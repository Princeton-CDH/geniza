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
    content_type = 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'

    def __init__(self, *args, **kwargs):
        super().__init__(content_type=self.content_type, *args, **kwargs)


class AnnotationList(
    PermissionRequiredMixin, ApiAccessMixin, View, MultipleObjectMixin
):
    model = Annotation
    http_method_names = ["get", "post"]

    paginate_by = None  # disable pagination for now

    def get_permission_required(self):
        # POST requires permission to create annotations
        if self.request.method == "POST":
            return (ANNOTATE_PERMISSION,)
        # GET doesn't require any permission
        return ()

    def get(self, request, *args, **kwargs):
        # strictly speaking, annotations endpoint should return an annotation container,
        annotations = self.get_queryset()
        # for now, just return json response with list of all annotations
        return AnnotationResponse(
            {"items": [a.compile() for a in annotations]},
        )

    def post(self, request, *args, **kwargs):
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
    model = Annotation
    http_method_names = ["get"]

    paginate_by = None  # disable pagination for now

    def get(self, request, *args, **kwargs):
        # implement minimal search by uri
        # implement something similar to SAS search by uri
        annotations = self.get_queryset()
        # if a target uri is specified, filter annotations
        target_uri = self.request.GET.get("uri")
        if target_uri:
            annotations = annotations.filter(content__target__source__id=target_uri)
        # NOTE: if any params are ignored, they should be removed from id for search uri
        # and documented in the response as ignored

        # return json response with list of annotations,
        # in basic AnnotationList format
        # TODO: eventually we may want pagination
        # (probably not needed for target uri searches)
        return JsonResponse(
            {
                "@context": "http://iiif.io/api/presentation/2/context.json",
                "@id": request.build_absolute_uri(),
                "@type": "sc:AnnotationList",
                "resources": [a.compile() for a in annotations],
            },
        )


class AnnotationDetail(
    PermissionRequiredMixin, ApiAccessMixin, View, SingleObjectMixin
):
    model = Annotation
    http_method_names = ["get", "post", "delete", "head"]

    def get(self, request, *args, **kwargs):
        # display as json on get
        anno = self.get_object()
        return AnnotationResponse(anno.compile())

    def get_permission_required(self):
        # POST and DELETE require permission to modify/remove annotations
        if self.request.method in ["POST", "DELETE"]:
            return (ANNOTATE_PERMISSION,)
        # GET/HEAD don't require any permissions
        else:
            return ()

    def post(self, request, *args, **kwargs):
        # update on post
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
        # should use etag / if-match
        # deleted uuid should not be reused (relying on low likelihood of uuid collision)
        anno = self.get_object()
        # create log entry to document deletion *BEFORE* deleting
        anno_admin = AnnotationAdmin(model=Annotation, admin_site=admin.site)
        anno_admin.log_deletion(request, anno, repr(anno))
        # then delete
        anno.delete()
        return HttpResponse(status=204)
