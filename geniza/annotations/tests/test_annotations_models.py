from unittest.mock import patch

import pytest
from django.urls import reverse

from geniza.annotations.models import Annotation
from geniza.common.utils import absolutize_url
from geniza.footnotes.models import Footnote


class TestAnnotation:
    def test_repr(self):
        # unsaved annotation gets a uuid on instantiation
        anno = Annotation()
        assert repr(anno) == "<Annotation id:%s>" % anno.pk

    def test_get_absolute_url(self):
        anno = Annotation()
        assert anno.get_absolute_url() == "/annotations/%s/" % anno.pk

    def test_etag(self, annotation):
        old_etag = annotation.etag
        # should be surrounded by doublequotes
        assert old_etag[0] == old_etag[-1] == '"'
        # should be length of an md5 hash + two characters
        assert len(old_etag) == 34
        # changing content should change etag
        annotation.content.update(
            {
                "foo": "bar",
                "id": "bogus",
                "created": "yesterday",
                "modified": "today",
            }
        )
        assert annotation.etag != old_etag
        new_etag = annotation.etag
        # changing other properties on the annotation should not change etag
        annotation.footnote = Footnote()
        assert annotation.etag == new_etag

    @pytest.mark.django_db
    def test_uri(self):
        anno = Annotation()
        assert anno.uri() == absolutize_url("/annotations/%s/" % anno.pk)

    @pytest.mark.django_db
    def test_set_content(self, source, document):
        footnote = Footnote.objects.create(source=source, content_object=document)
        content = {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "id": absolutize_url("/annotations/1"),
            "type": "Annotation",
            "foo": "bar",
            "etag": "abcd1234",
        }
        anno = Annotation(footnote=footnote)
        anno.set_content(content)

        # check that appropriate fields were removed
        for field in ["@context", "id", "type", "etag"]:
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

        # should set source and manifest URIs based on footnote
        assert compiled["dc:source"] == annotation.footnote.source.uri
        assert (
            compiled["target"]["source"]["partOf"]["id"]
            == annotation.footnote.content_object.manifest_uri
        )

        # set via and canonical
        annotation.via = "http://example.com/annotations/123"
        annotation.canonical = "urn:uuid:123"
        compiled = annotation.compile()
        assert compiled["canonical"] == annotation.canonical
        assert compiled["via"] == annotation.via

        line = Annotation.objects.create(
            footnote=annotation.footnote, block=annotation, content={}
        )
        compiled = line.compile()
        assert compiled["partOf"] == annotation.uri()

        # when include_context=False (i.e. part of a list), should include etag, since
        # we need a way to associate individual ETag to each item returned in list response
        compiled = line.compile(include_context=False)
        assert compiled["etag"] == line.etag
        assert "@context" not in compiled

    def test_sanitize_html(self):
        html = '<table><div><p style="foo:bar;">test</p></div><ol><li>line</li></ol></table>'
        # should strip out all unwanted elements and attributes (table, div, style)
        # (\n is added because bleach replaces block-level elements with newline)
        assert Annotation.sanitize_html(html) == "\n<p>test</p><ol><li>line</li></ol>"

        # should do nothing to html with all allowed elements
        html = '<p>test <span lang="en">en</span></p><ol><li>line 1</li><li>line 2</li></ol>'
        assert Annotation.sanitize_html(html) == html

        # should remove span elements with no attributes after bleaching
        html = '<p>text <span style="foo:bar">and</span> more text</p>'
        assert Annotation.sanitize_html(html) == "<p>text and more text</p>"

        # should remove \xa0 Unicode non-breaking space
        html = "<p>text\xa0and more \xa0 text</p>"
        assert Annotation.sanitize_html(html) == "<p>text and more text</p>"

    def test_block_content_html(self, annotation):
        annotation.content["body"][0]["label"] = "Test label"
        # should include label and content
        block_html = annotation.block_content_html
        assert len(block_html) == 2
        assert block_html[0] == "<h3>Test label</h3>"
        assert block_html[1] == annotation.body_content

        # with associated lines, should produce ordered list
        del annotation.content["body"][0]["value"]
        line_1 = Annotation.objects.create(
            block=annotation,
            content={"body": [{"value": "Line 1"}], "schema:position": 1},
            footnote=annotation.footnote,
        )
        line_2 = Annotation.objects.create(
            block=annotation,
            content={"body": [{"value": "Line 2"}], "schema:position": 2},
            footnote=annotation.footnote,
        )

        # invalidate cached properties
        del annotation.has_lines
        del annotation.block_content_html

        # should now show that it has lines and produce the ordered list
        assert annotation.has_lines == True
        block_html = annotation.block_content_html
        assert len(block_html) == 5
        assert block_html[0] == "<h3>Test label</h3>"
        assert block_html[1] == "<ol>"
        assert block_html[2] == f"<li>{line_1.body_content}</li>"
        assert block_html[3] == f"<li>{line_2.body_content}</li>"


@pytest.mark.django_db
class TestAnnotationQuerySet:
    def test_by_target_context(self, annotation, join):
        # join fixture not in annotation; should get none back
        annos = Annotation.objects.by_target_context(join.manifest_uri)
        assert not annos.exists()

        anno_manifest = annotation.target_source_manifest_id
        annos = Annotation.objects.by_target_context(anno_manifest)
        assert annos.count() == 1
        assert annos.first() == annotation

    def test_group_by_canvas(self, annotation):
        # copy fixture annotation to make a second annotation on the same canvas
        anno2 = Annotation.objects.create(
            footnote=annotation.footnote,
            content={
                "target": {"source": {"id": annotation.target_source_id}},
                "body": [{"value": "foo"}],
            },
        )
        other_canvas = "http://ex.co/iiif/canvas/3421"
        other_anno = Annotation.objects.create(
            footnote=annotation.footnote,
            content={
                "target": {"source": {"id": other_canvas}},
                "body": [{"value": "bar"}],
            },
        )
        # should be ignored but not cause an error
        no_target_anno = Annotation.objects.create(
            footnote=annotation.footnote, content={"body": [{"value": "foo bar"}]}
        )

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

    def test_group_by_manifest(self, annotation, join, source):
        # copy fixture annotation to make a second annotation on the same manifest
        anno2 = Annotation.objects.create(
            footnote=annotation.footnote,
            content={
                "body": [{"value": "foo bar"}],
                "target": {
                    "source": {
                        "id": annotation.target_source_id,
                    }
                },
            },
        )
        # and another annotation on a different manifest
        other_footnote = Footnote.objects.create(source=source, content_object=join)

        other_anno = Annotation.objects.create(
            footnote=other_footnote,
            content={
                "body": [{"value": "foo bar baz"}],
                "target": {
                    "source": {
                        "id": annotation.target_source_id,
                    }
                },
            },
        )
        # should be ignored but not cause an error
        no_target_anno = Annotation.objects.create(
            footnote=other_footnote, content={"body": [{"value": "foo"}]}
        )

        annos_by_manifest = Annotation.objects.all().group_by_manifest()
        # expect two manifest uris
        assert len(annos_by_manifest.keys()) == 2
        # two annotations for fixture anno manifest
        assert len(annos_by_manifest[annotation.target_source_manifest_id]) == 2
        # check annotations are present where they should be
        assert annotation in annos_by_manifest[annotation.target_source_manifest_id]
        assert anno2 in annos_by_manifest[annotation.target_source_manifest_id]

        # one for the other canvas
        assert len(annos_by_manifest[join.manifest_uri]) == 1
        assert other_anno in annos_by_manifest[join.manifest_uri]
