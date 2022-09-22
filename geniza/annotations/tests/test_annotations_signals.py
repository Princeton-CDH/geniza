from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from parasolr.django.indexing import ModelIndexable

from geniza.annotations.models import Annotation
from geniza.annotations.signals import backup_annotation
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


@patch("geniza.annotations.signals.AnnotationExporter")
def test_backup_annotation(mock_annoexporter, annotation):
    doc_id = Document.id_from_manifest_uri(annotation.target_source_manifest_id)
    backup_annotation(doc_id, annotation)

    # should export this document only without pushing changes or coauthors
    mock_annoexporter.assert_called_with(
        pgpids=[doc_id], push_changes=False, modifying_users=[]
    )
    mock_annoexporter.return_value.export.assert_called()


@patch("geniza.annotations.signals.AnnotationExporter")
def test_backup_annotation_coauthor(mock_annoexporter, annotation):
    doc_id = Document.id_from_manifest_uri(annotation.target_source_manifest_id)
    # create a log entry to check finding user for coauthor
    # get script user
    script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
    # create a test user with a profile
    editor = User.objects.create(username="editor", last_name="Editor", first_name="Ma")

    anno_ctype = ContentType.objects.get_for_model(Annotation)
    LogEntry.objects.log_action(
        user_id=editor.id,
        content_type_id=anno_ctype.pk,
        object_id=annotation.pk,
        object_repr=str(annotation),
        change_message="test log entry",
        action_flag=CHANGE,
    )
    # earlier log entry for different user should be ignored
    LogEntry.objects.create(
        user_id=script_user.id,
        content_type_id=anno_ctype.pk,
        object_id=annotation.pk,
        object_repr=str(annotation),
        action_flag=ADDITION,
        change_message="earlier log entry",
        action_time=timezone.now() - timedelta(seconds=65),
    )

    backup_annotation(doc_id, annotation)

    # should export this document only, with coauthor specified
    mock_annoexporter.assert_called_with(
        pgpids=[doc_id], push_changes=False, modifying_users=[editor]
    )
