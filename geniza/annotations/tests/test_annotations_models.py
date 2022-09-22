from unittest.mock import patch

import pytest
from django.urls import reverse

from geniza.annotations.models import Annotation
from geniza.common.utils import absolutize_url


class TestAnnotation:
    def test_repr(self):
        # unsaved annotation gets a uuid on instantiation
        anno = Annotation()
        assert repr(anno) == "<Annotation id:%s>" % anno.pk

    def test_get_absolute_url(self):
        anno = Annotation()
        assert anno.get_absolute_url() == "/annotations/%s/" % anno.pk

    @pytest.mark.django_db
    def test_uri(self):
        anno = Annotation()
        assert anno.uri() == absolutize_url("/annotations/%s/" % anno.pk)

    @pytest.mark.django_db
    def test_set_content(self):
        content = {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "id": absolutize_url("/annotations/1"),
            "type": "Annotation",
            "foo": "bar",
        }
        anno = Annotation()
        anno.set_content(content)

        # check that appropriate fields were removed
        for field in ["@context", "id", "type"]:
            assert field not in anno.content
        # remaining content was set
        assert anno.content["foo"] == "bar"

        # set via and canonical
        content["canonical"] = "urn:uuid:123"
        content["via"] = "http://example.com/annotations/123"
        content["foo"] = "bar baz"
        anno.set_content(content)
        # canonical and via are set, and removed from content data
        assert anno.canonical == "urn:uuid:123"
        assert anno.via == "http://example.com/annotations/123"
        assert "canonical" not in anno.content
        assert "via" not in anno.content
        # remaining content was set
        assert anno.content["foo"] == "bar baz"

        # should refuse to update if via or canonical differs
        bad_content = content.copy()
        bad_content["canonical"] = "urn:uuid:456"
        with pytest.raises(ValueError):
            anno.set_content(bad_content)

        bad_content = content.copy()
        bad_content["via"] = "http://example.com/annotations/456"
        with pytest.raises(ValueError):
            anno.set_content(bad_content)

        # should call sanitize_html on body value
        with patch.object(Annotation, "sanitize_html") as mock_sanitize:
            content_with_body = content.copy()
            content_with_body["body"] = [{"value": "some html"}]
            anno.set_content(content_with_body)
            mock_sanitize.assert_called_once_with("some html")
            mock_sanitize.reset_mock()

            # should not call sanitize_html if no body
            anno.set_content(content)
            mock_sanitize.assert_not_called

    @pytest.mark.django_db
    def test_compile(self, annotation):
        # create so we get id, created, modified
        annotation.content.update(
            {
                "foo": "bar",
                "id": "bogus",
                "created": "yesterday",
                "modified": "today",
            }
        )
        compiled = annotation.compile()

        # fields from model should take precedence if there's any collison with content
        assert compiled["id"] == annotation.uri()
        assert compiled["@context"] == "http://www.w3.org/ns/anno.jsonld"
        assert compiled["type"] == "Annotation"
        assert compiled["created"] == annotation.created.isoformat()
        assert compiled["modified"] == annotation.modified.isoformat()
        # content should be set
        assert compiled["foo"] == "bar"
        # canonical and via should not be set
        assert "canonical" not in compiled
        assert "via" not in compiled

        # set via and canonical
        annotation.via = "http://example.com/annotations/123"
        annotation.canonical = "urn:uuid:123"
        compiled = annotation.compile()
        assert compiled["canonical"] == annotation.canonical
        assert compiled["via"] == annotation.via

    def test_sanitize_html(self):
        html = '<table><div><p style="foo:bar;">test</p></div><ol><li>line</li></ol></table>'
        # should strip out all unwanted elements and attributes (table, div, style)
        # (\n is added because bleach replaces block-level elements with newline)
        assert Annotation.sanitize_html(html) == "\n<p>test</p><ol><li>line</li></ol>"

        # should do nothing to html with all allowed elements
        html = '<p>test <span lang="en">en</span></p><ol><li>line 1</li><li>line 2</li></ol>'
        assert Annotation.sanitize_html(html) == html


@pytest.mark.django_db
class TestAnnotationQuerySet:
    def test_by_target_context(self, annotation, document):
        # document fixture not in annotation; should get none back
        annos = Annotation.objects.by_target_context(document.manifest_uri)
        assert not annos.exists()

        anno_manifest = annotation.target_source_manifest_id
        print(anno_manifest)
        annos = Annotation.objects.by_target_context(anno_manifest)
        assert annos.count() == 1
        assert annos.first() == annotation

    def test_group_by_canvas(self, annotation):
        # copy fixture annotation to make a second annotation on the same canvas
        anno2 = Annotation.objects.create(
            content={
                "target": {"source": {"id": annotation.target_source_id}},
            }
        )
        other_canvas = "http://ex.co/iiif/canvas/3421"
        other_anno = Annotation.objects.create(
            content={
                "target": {"source": {"id": other_canvas}},
            }
        )
        # should be ignored but not cause an error
        no_target_anno = Annotation.objects.create(content={"body": "foo"})

        annos_by_canvas = Annotation.objects.all().group_by_canvas()
        # expect two canvas uris
        assert len(annos_by_canvas.keys()) == 2
        # two annotations for fixture anno canvas
        assert len(annos_by_canvas[annotation.target_source_id]) == 2
        # check annotations are present where they should be
        assert annotation in annos_by_canvas[annotation.target_source_id]
        assert anno2 in annos_by_canvas[annotation.target_source_id]

        # one for the other canvas
        assert len(annos_by_canvas[other_canvas]) == 1
        assert other_anno in annos_by_canvas[other_canvas]
