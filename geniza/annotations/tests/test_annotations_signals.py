from unittest.mock import patch

from django.contrib.admin.models import ADDITION, DELETION, LogEntry
from django.urls import reverse
from parasolr.django.indexing import ModelIndexable

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Source


class TestCreateOrDeleteFootnote:
    def test_create_annotation(self, document, source):
        # should create a DIGITAL_EDITION footnote if one does not exist
        assert not document.digital_editions().filter(source=source).exists()
        Annotation.objects.create(
            content={
                "body": [{"value": "Test annotation"}],
                "target": {
                    "source": {
                        "partOf": {
                            "id": reverse(
                                "corpus:document-manifest", kwargs={"pk": document.pk}
                            )
                        }
                    }
                },
                "dc:source": source.uri,
            }
        )
        # will raise error if digital edition footnote does not exist
        footnote = document.digital_editions().get(source=source)

        # should log action
        assert LogEntry.objects.filter(
            object_id=footnote.pk, action_flag=ADDITION
        ).exists()

    def test_delete_last_annotation(self, annotation):
        # Should delete footnote if deleted annotation is the only annotation on source + document
        manifest_uri = annotation.content["target"]["source"]["partOf"]["id"]
        source_uri = annotation.content["dc:source"]
        source = Source.from_uri(source_uri)
        document = Document.from_manifest_uri(manifest_uri)
        # will raise error if digital edition footnote does not exist
        footnote = document.digital_editions().get(source=source)
        annotation.delete()
        assert not document.digital_editions().filter(source=source).exists()

        # should log action (DELETION has no object_id)
        assert LogEntry.objects.filter(
            object_repr=str(footnote),
            change_message__contains="Footnote automatically deleted via deleted annotation",
            action_flag=DELETION,
        ).exists()

        # Should not delete footnote if there are more annotations on source + document
        annotation2 = Annotation.objects.create(content=annotation.content)
        Annotation.objects.create(
            content={**annotation.content, "body": [{"value": "other"}]}
        )
        annotation2.delete()
        document = Document.from_manifest_uri(manifest_uri)
        assert document.digital_editions().filter(source=source).exists()

    @patch.object(ModelIndexable, "index_items")
    def test_update_annotation(self, mock_indexitems, annotation):
        # should call index_items on document when annotation updated
        manifest_uri = annotation.content["target"]["source"]["partOf"]["id"]
        document = Document.from_manifest_uri(manifest_uri)
        annotation.content = {**annotation.content, "body": [{"value": "new value"}]}
        annotation.save()
        mock_indexitems.assert_called_with([document])
