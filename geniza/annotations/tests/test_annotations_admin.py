import pytest
from django.contrib import admin

from geniza.annotations.admin import AnnotationAdmin
from geniza.annotations.models import Annotation


class TestAnnotationAdmin:
    def test_display_content(self):
        anno = Annotation(content={"foo": "bar"})
        admin_form = AnnotationAdmin(model=Annotation, admin_site=admin.site)
        display_content = admin_form.display_content(anno)
        # should escape HTML characters within content
        assert display_content == "<pre>{&#x27;foo&#x27;: &#x27;bar&#x27;}</pre>"

    def test_pgpid(self, annotation, document):
        admin_form = AnnotationAdmin(model=Annotation, admin_site=admin.site)

        # set a geniza manifest and retrieve the id
        assert admin_form.pgpid(annotation) == document.pk

    def test_target_id(self):
        anno = Annotation(content={"foo": "bar"})
        admin_form = AnnotationAdmin(model=Annotation, admin_site=admin.site)
        # should not error if not present in content
        assert admin_form.target_id(anno) is None

        # set a geniza target and retrieve the id
        test_canvas_id = ("http://geniza.cdh/documents/123/iiif/canvas/1",)
        anno.content = {"target": {"source": {"id": test_canvas_id}}}
        assert admin_form.target_id(anno) == test_canvas_id
