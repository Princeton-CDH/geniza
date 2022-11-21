from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from geniza.annotations.models import Annotation
from geniza.annotations.signals import backup_annotation
from geniza.corpus.annotation_utils import document_id_from_manifest_uri


@patch("geniza.annotations.signals.AnnotationExporter")
def test_backup_annotation(mock_annoexporter, annotation):
    doc_id = document_id_from_manifest_uri(annotation.target_source_manifest_id)
    backup_annotation(doc_id, annotation)

    # should export this document only without pushing changes or coauthors
    mock_annoexporter.assert_called_with(
        pgpids=[doc_id], push_changes=False, modifying_users=[]
    )
    mock_annoexporter.return_value.export.assert_called()


@patch("geniza.annotations.signals.AnnotationExporter")
def test_backup_annotation_coauthor(mock_annoexporter, annotation):
    doc_id = document_id_from_manifest_uri(annotation.target_source_manifest_id)
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
