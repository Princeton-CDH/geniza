import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin

from geniza.annotations.models import Annotation


class AnnotationResponse(JsonResponse):
    content_type = 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'


@method_decorator(csrf_exempt, name="dispatch")  # disable csrf for testing with curl
class AnnotationList(View, MultipleObjectMixin):
    model = Annotation
    http_method_names = ["get", "post"]

    def get(self, request, *args, **kwargs):
        # strictly speaking, annotations endpoint should return an annotation container,
        # but that structure looks terrible to work with and we need a way to search,
        # which is not defined in the w3c annotation protocol.
        annotations = Annotation.objects.all()
        # implement something similar to SAS search by uri

        # if a target uri is specified, filter annotations
        target_uri = request.GET.get("target_uri")
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
class AnnotationDetail(View, SingleObjectMixin):
    model = Annotation
    http_method_names = ["get", "post", "delete"]

    def get(self, request, *args, **kwargs):
        # display as json on get
        anno = self.get_object()
        return AnnotationResponse(anno.compile())

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
