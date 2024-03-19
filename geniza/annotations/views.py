import json
import logging

from django.contrib import admin
from django.contrib.admin.models import ADDITION, DELETION, LogEntry
from django.contrib.auth.mixins import AccessMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import BadRequest
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import condition
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from geniza.annotations.admin import AnnotationAdmin
from geniza.annotations.models import Annotation, annotations_to_list
from geniza.corpus.annotation_utils import document_id_from_manifest_uri
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source

# NOTE: for PGP, anyone with permission to edit documents
# should also have permission to edit or create transcriptions.
# So, we only check for change document permission
# instead of add, change, delete annotation permissions.
ANNOTATE_PERMISSION = "corpus.change_document"

logger = logging.getLogger(__name__)


class ApiAccessMixin(AccessMixin):
    raise_exception = True  # return an error instead of redirecting to login


class AnnotationLastModifiedMixin(View):
    """View mixin to add ETag/last modified headers."""

    def get_etag(self, request, *args, **kwargs):
        """Get etag from annotation"""
        try:
            anno = Annotation.objects.get(pk=kwargs.get("pk"))
            return anno.etag
        except Annotation.DoesNotExist:
            return None

    def get_last_modified(self, request, *args, **kwargs):
        """Return last modified :class:`datetime.datetime`"""
        try:
            anno = Annotation.objects.get(pk=kwargs.get("pk"))
            return anno.modified
        except Annotation.DoesNotExist:
            return None

    def dispatch(self, request, *args, **kwargs):
        """Wrap the dispatch method to add ETag/last modified headers when
        appropriate, then return a conditional response."""

        @condition(etag_func=self.get_etag, last_modified_func=self.get_last_modified)
        def _dispatch(request, *args, **kwargs):
            return super(AnnotationLastModifiedMixin, self).dispatch(
                request, *args, **kwargs
            )

        return _dispatch(request, *args, **kwargs)


class AnnotationResponse(JsonResponse):
    """Base class for annotation responses; extends json response to set
    annotation profile content type."""

    content_type = 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'

    def __init__(self, *args, **kwargs):
        super().__init__(content_type=self.content_type, *args, **kwargs)


def parse_annotation_data(request):
    """
    For annotation create and update methods, parse json data from request in order
    to set/update associated footnote. Returns content dict and footnote object.
    """
    json_data = json.loads(request.body)

    # get manifest and source URIs and resolve to source and document
    manifest_uri = json_data["target"]["source"]["partOf"]["id"]
    source_uri = json_data["dc:source"]
    source_id = Source.id_from_uri(source_uri)
    document_id = document_id_from_manifest_uri(manifest_uri)
    document_contenttype = ContentType.objects.get_for_model(Document)

    # remove references to manifest and source URIs from content before save
    del json_data["target"]["source"]["partOf"]
    del json_data["dc:source"]

    # determine if this is a transcription or translation
    if "motivation" in json_data and "translating" in json_data["motivation"]:
        doc_relation = Footnote.DIGITAL_TRANSLATION
        corresponding_relation = Footnote.TRANSLATION
    else:
        doc_relation = Footnote.DIGITAL_EDITION
        corresponding_relation = Footnote.EDITION

    # find or create DIGITAL_EDITION footnote for this source and document
    try:
        footnote = Footnote.objects.get(
            doc_relation=[doc_relation],
            source__pk=source_id,
            content_type=document_contenttype,
            object_id=document_id,
        )
    except Footnote.DoesNotExist:
        source = Source.objects.get(pk=source_id)

        # try to find a corresponding non-digital footnote for location field
        # (i.e. Translation for Digital Translation, Edition for Digital Edition)
        # NOTE: assumes that if there is exactly one non-digital footnote for this source, then
        # the digital content is coming from the same location
        try:
            # use .get to ensure there is exactly one corresponding;
            # otherwise ambiguous which location to use
            corresponding_footnote = Footnote.objects.exclude(location="").get(
                doc_relation__contains=corresponding_relation,
                source__pk=source_id,
                content_type=document_contenttype,
                object_id=document_id,
            )
            location = corresponding_footnote.location
        except (Footnote.DoesNotExist, Footnote.MultipleObjectsReturned):
            # if there are 0 or > 1 footnotes, location should be blank
            location = ""

        # create a new digital footnote
        footnote = Footnote.objects.create(
            source=source,
            doc_relation=[doc_relation],
            object_id=document_id,
            content_type=document_contenttype,
            location=location,
        )
        LogEntry.objects.log_action(
            user_id=request.user.id,
            content_type_id=ContentType.objects.get_for_model(Footnote).pk,
            object_id=footnote.pk,
            object_repr=str(footnote),
            action_flag=ADDITION,
            change_message=f"Footnote automatically created via created annotation.",
        )

    return {"content": json_data, "footnote": footnote}


class AnnotationList(
    PermissionRequiredMixin, ApiAccessMixin, View, MultipleObjectMixin
):
    """Base annotation endpoint; on GET, returns an annotation collection;
    on POST with valid credentials and permissions, creates a new annotation."""

    model = Annotation
    http_method_names = ["get", "post"]

    paginate_by = 100

    def get_permission_required(self):
        """return permission required based on request method"""
        # POST requires permission to create annotations
        if self.request.method == "POST":
            return (ANNOTATE_PERMISSION,)
        # GET doesn't require any permission
        return ()

    def get(self, request, *args, **kwargs):
        "generate annotation collection response on GET request"
        # populate paginated queryset
        paginator = self.get_paginator(self.get_queryset(), self.paginate_by)

        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        annotations = page_obj.object_list

        # get current uri without any params
        request_uri = request.build_absolute_uri().split("?")[0]
        current_page_params = request.GET.copy()
        current_page_params["page"] = page_number
        next_page_params = None
        if page_obj.has_next():
            next_page_params = request.GET.copy()
            next_page_params["page"] = page_obj.next_page_number()
        last_page_params = request.GET.copy()
        last_page_params["page"] = page_obj.end_index()

        # simple annotation collection reponse without pagination
        response_data = {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "type": "AnnotationCollection",
            "id": request_uri,
            "total": paginator.count,
            "modified": paginator.object_list.last().modified.isoformat(),
            "label": "Princeton Geniza Project Web Annotations",
            "first": {
                "id": "%s?%s" % (request_uri, current_page_params.urlencode()),
                "type": "AnnotationPage",
                # "next": "http://example.org/annotations/?iris=1&page=1",
                # display items for the current page of results;
                # only support full record view for now
                "items": [a.compile(include_context=False) for a in annotations],
            },
            "last": "%s?%s" % (request_uri, last_page_params.urlencode()),
        }
        # add next page link if there is one
        if next_page_params:
            response_data["first"]["next"] = "%s?%s" % (
                request_uri,
                next_page_params.urlencode(),
            )

        return AnnotationResponse(response_data)

    def post(self, request, *args, **kwargs):
        """ "Create a new annotation"""

        # parse request content as json
        anno = Annotation()
        try:
            anno_data = parse_annotation_data(request=request)
        except (KeyError, IndexError):
            raise BadRequest(Annotation.MALFORMED_ERROR)
        anno.set_content(anno_data["content"])
        anno.footnote = anno_data["footnote"]

        # create log entry
        anno_admin = AnnotationAdmin(model=Annotation, admin_site=admin.site)
        anno_admin.log_addition(request, anno, "Created via API")

        anno.save()

        # create and send response
        resp = AnnotationResponse(anno.compile())
        resp.status_code = 201  # created
        # location header must include annotation's new uri
        resp.headers["Location"] = anno.uri()

        return resp


class AnnotationSearch(View, MultipleObjectMixin):
    """Simple seach endpoint based on IIIF Search API.
    Returns an annotation list response."""

    model = Annotation
    http_method_names = ["get"]

    paginate_by = None  # disable pagination for now

    def get(self, request, *args, **kwargs):
        """Search annotations and return an annotation list. Currently only supports
        search by target uri and source uri."""
        # TODO: Convert this to list when > 2 options
        # implement minimal search by uri
        # implement something similar to SAS search by uri

        # sort by schema:position if available
        annotations = self.get_queryset().order_by(
            "content__schema:position", "created"
        )
        # if a target uri is specified, filter annotations
        target_uri = self.request.GET.get("uri")
        if target_uri:
            annotations = annotations.filter(content__target__source__id=target_uri)
        source_uri = self.request.GET.get("source")
        # if a source uri is specified, filter on source via footnote
        if source_uri:
            source_id = Source.id_from_uri(source_uri)
            annotations = annotations.filter(footnote__source__pk=source_id)

        manifest_uri = self.request.GET.get("manifest")
        # if a manifest uri is specified, filter on document via footnote
        if manifest_uri:
            pgpid = document_id_from_manifest_uri(manifest_uri)
            annotations = annotations.filter(
                footnote__object_id=pgpid, footnote__content_type__model="document"
            )

        motivation = self.request.GET.get("motivation")
        # if a motivation is specified, filter on doc relation
        if motivation:
            annotations = annotations.filter(
                footnote__doc_relation=Footnote.DIGITAL_TRANSLATION
                if motivation == "translating"
                else Footnote.DIGITAL_EDITION
            )

        # NOTE: if any params are ignored, they should be removed from id for search uri
        # and documented in the response as ignored

        # return json response with list of annotations,
        # in basic AnnotationList format
        # TODO: eventually we may want pagination
        # (probably not needed for target uri searches)
        return JsonResponse(
            annotations_to_list(annotations, uri=request.build_absolute_uri())
        )


class AnnotationDetail(
    PermissionRequiredMixin,
    AnnotationLastModifiedMixin,
    ApiAccessMixin,
    View,
    SingleObjectMixin,
):
    """View to read, update, or delete a single annotation."""

    model = Annotation
    http_method_names = ["get", "post", "delete", "head"]

    def get(self, request, *args, **kwargs):
        """display as annotation"""
        # display as json on get
        anno = self.get_object()
        return AnnotationResponse(anno.compile())

    def get_permission_required(self):
        """return permission required based on request method"""
        # POST and DELETE require permission to modify/remove annotations
        if self.request.method in ["POST", "DELETE"]:
            return (ANNOTATE_PERMISSION,)
        # GET/HEAD don't require any permissions
        else:
            return ()

    def post(self, request, *args, **kwargs):
        """update the annotation on POST"""
        anno = self.get_object()
        try:
            anno_data = parse_annotation_data(request=request)
        except (KeyError, IndexError):
            raise BadRequest(Annotation.MALFORMED_ERROR)
        anno.set_content(anno_data["content"])
        # if changed, save and create log entry, and reindex document
        if any(
            anno.has_changed(f)
            for f in ["content", "canonical", "via"]
            or anno.footnote.pk != anno_data["footnote"]
        ):
            anno.footnote = anno_data["footnote"]
            # create log entry to document change
            anno_admin = AnnotationAdmin(model=Annotation, admin_site=admin.site)
            anno_admin.log_change(request, anno, "Updated via API")
            anno.save()

        return AnnotationResponse(anno.compile())

    def delete(self, request, *args, **kwargs):
        """delete the annotation on DELETE"""
        # deleted uuid should not be reused (relying on low likelihood of uuid collision)
        anno = self.get_object()
        # create log entry to document deletion *BEFORE* deleting
        annotation_ctype = ContentType.objects.get_for_model(Annotation)
        LogEntry.objects.log_action(
            user_id=request.user.id,
            content_type_id=annotation_ctype.pk,
            object_id=anno.pk,
            object_repr=repr(anno),
            # store manifest and target in change message, so we can
            # update transcription exports after the annotation is gone
            change_message=json.dumps(
                {
                    "manifest_uri": anno.target_source_manifest_id,
                    "target_source_uri": anno.target_source_id,
                }
            ),
            action_flag=DELETION,
        )
        footnote = anno.footnote

        # then delete
        anno.delete()

        # update footnote to remove DIGITAL_EDITION type if this is the last annotation associated with it
        footnote.refresh_from_db()
        if footnote.annotation_set.count() == 0:
            if Footnote.DIGITAL_EDITION in footnote.doc_relation:
                footnote.doc_relation.remove(Footnote.DIGITAL_EDITION)
            if Footnote.DIGITAL_TRANSLATION in footnote.doc_relation:
                footnote.doc_relation.remove(Footnote.DIGITAL_TRANSLATION)
            footnote.save()
            footnote.refresh_from_db()

        return HttpResponse(status=204)
