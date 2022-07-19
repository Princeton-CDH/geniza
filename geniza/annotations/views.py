import json

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from geniza.annotations.models import Annotation

# NOTE: for PGP, anyone with permission to edit documents
# should also have permission to edit or create transcriptions.
# So, we only check for change document permission
# instead of add, change, delete annotation permissions.
ANNOTATE_PERMISSION = "corpus.change_document"


class AnnotationResponse(JsonResponse):
    content_type = 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'


@method_decorator(csrf_exempt, name="dispatch")  # disable csrf for testing with curl
class AnnotationList(PermissionRequiredMixin, View, MultipleObjectMixin):
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
        # but that structure looks terrible to work with and we need a way to search,
        # which is not defined in the w3c annotation protocol.

        # implement something similar to SAS search by uri
        annotations = self.get_queryset()
        # if a target uri is specified, filter annotations
        target_uri = self.request.GET.get("target_uri")
        if target_uri:
            annotations = annotations.filter(content__target__source__id=target_uri)

        # return json response with list of annotations
        # TODO: eventually we'll need to limit or paginate this
        return AnnotationResponse(
            {"items": [a.compile() for a in annotations]},
        )

    # todo check perms
    def post(self, request, *args, **kwargs):
        # parse request content as json
        json_data = json.loads(request.body)
        anno = Annotation()
        anno.set_content(json_data)
        anno.save()
        resp = AnnotationResponse(anno.compile())
        resp.status_code = 201  # created
        # location header must include annotation's new uri
        resp.location = anno.uri()

        # TODO: should we create log entries to document activity?

        return resp


@method_decorator(csrf_exempt, name="dispatch")  # disable csrf for testing
class AnnotationDetail(PermissionRequiredMixin, View, SingleObjectMixin):
    model = Annotation
    http_method_names = ["get", "post", "delete"]

    def get(self, request, *args, **kwargs):
        # display as json on get
        anno = self.get_object()
        return AnnotationResponse(anno.compile())

    def get_permission_required(self):
        # GET doesn't require any permission
        if self.request.method == "GET":
            return ()
        # POST and DELETE require permission to create annotations
        else:
            return (ANNOTATE_PERMISSION,)

    def post(self, request, *args, **kwargs):
        # update on post
        # should use etag / if-match
        anno = self.get_object()
        json_data = json.loads(request.body)
        anno.set_content(json_data)
        anno.save()
        print("there are now %d annotations" % Annotation.objects.count())
        # TODO: create log entry?

        return AnnotationResponse(anno.compile())

    def delete(self, request, *args, **kwargs):
        # should use etag / if-match
        # deleted uuid should not be reused (relying on low likelihood of uuid collision)
        anno = self.get_object()
        anno.delete()

        # TODO: create log entry?
        return HttpResponse(status=204)
