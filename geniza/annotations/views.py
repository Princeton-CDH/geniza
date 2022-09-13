import json

from django.contrib import admin
from django.contrib.auth.mixins import AccessMixin, PermissionRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from geniza.annotations.admin import AnnotationAdmin
from geniza.annotations.models import Annotation

# NOTE: for PGP, anyone with permission to edit documents
# should also have permission to edit or create transcriptions.
# So, we only check for change document permission
# instead of add, change, delete annotation permissions.
ANNOTATE_PERMISSION = "corpus.change_document"


class ApiAccessMixin(AccessMixin):
    raise_exception = True  # return an error instead of redirecting to login


class AnnotationResponse(JsonResponse):
    """Base class for annotation responses; extends json response to set
    annotation profile content type."""

    content_type = 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'

    def __init__(self, *args, **kwargs):
        super().__init__(content_type=self.content_type, *args, **kwargs)


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
        json_data = json.loads(request.body)
        anno = Annotation()
        anno.set_content(json_data)
        anno.save()
        resp = AnnotationResponse(anno.compile())
        resp.status_code = 201  # created
        # location header must include annotation's new uri
        resp.headers["Location"] = anno.uri()

        anno_admin = AnnotationAdmin(model=Annotation, admin_site=admin.site)
        anno_admin.log_addition(request, anno, "Created via API")

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
        # if a source uri is specified, filter on content__dc:source
        if source_uri:
            annotations = annotations.filter(
                content__contains={"dc:source": source_uri}
            )

        manifest_uri = self.request.GET.get("manifest")
        # if a manifest uri is specified, filter on target source within
        if manifest_uri:
            annotations = annotations.filter(
                content__target__source__partOf__id=manifest_uri
            )

        # NOTE: if any params are ignored, they should be removed from id for search uri
        # and documented in the response as ignored

        # return json response with list of annotations,
        # in basic AnnotationList format
        # TODO: eventually we may want pagination
        # (probably not needed for target uri searches)
        return JsonResponse(
            {
                "@context": "http://iiif.io/api/presentation/2/context.json",
                "@id": request.build_absolute_uri(),  # @id and not id per iiif search spec
                "@type": "sc:AnnotationList",
                # context seems to be not required within AnnotationList
                "resources": [a.compile(include_context=False) for a in annotations],
            },
        )


class AnnotationDetail(
    PermissionRequiredMixin, ApiAccessMixin, View, SingleObjectMixin
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
        # should use etag / if-match
        anno = self.get_object()
        json_data = json.loads(request.body)
        anno.set_content(json_data)
        anno.save()

        # create log entry to document change
        anno_admin = AnnotationAdmin(model=Annotation, admin_site=admin.site)
        anno_admin.log_change(request, anno, "Updated via API")
        return AnnotationResponse(anno.compile())

    def delete(self, request, *args, **kwargs):
        """delete the annotation on DELETE"""
        # should use etag / if-match
        # deleted uuid should not be reused (relying on low likelihood of uuid collision)
        anno = self.get_object()
        # create log entry to document deletion *BEFORE* deleting
        anno_admin = AnnotationAdmin(model=Annotation, admin_site=admin.site)
        anno_admin.log_deletion(request, anno, repr(anno))
        # then delete
        anno.delete()
        return HttpResponse(status=204)
