import pytest

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

    @pytest.mark.django_db
    def test_compile(self):
        # create so we get id, created, modified
        anno = Annotation.objects.create(
            content={
                "foo": "bar",
                "id": "bogus",
                "created": "yesterday",
                "modified": "today",
            }
        )
        compiled = anno.compile()

        # fields from model should take precedence if there's any collison with content
        assert compiled["id"] == anno.uri()
        assert compiled["@context"] == "http://www.w3.org/ns/anno.jsonld"
        assert compiled["type"] == "Annotation"
        assert compiled["created"] == anno.created.isoformat()
        assert compiled["modified"] == anno.modified.isoformat()
        # content should be set
        assert compiled["foo"] == "bar"
        # canonical and via should not be set
        assert "canonical" not in compiled
        assert "via" not in compiled

        # set via and canonical
        anno.via = "http://example.com/annotations/123"
        anno.canonical = "urn:uuid:123"
        compiled = anno.compile()
        assert compiled["canonical"] == anno.canonical
        assert compiled["via"] == anno.via
