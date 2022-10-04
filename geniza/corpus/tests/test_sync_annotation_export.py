import json
from datetime import datetime
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone

from geniza.annotations.models import Annotation
from geniza.corpus.management.commands import sync_annotation_export
from geniza.corpus.models import Document


class TestSyncAnnationExport:
    def test_get_lastrun_info(self, tmpdir):
        cmd = sync_annotation_export.Command()
        cmd.lastrun_filename = tmpdir / "test_lastrun"

        # no last run file, returns None
        assert not cmd.lastrun_filename.exists()
        assert cmd.get_lastrun_info() is None

        # put something there and check we get it back
        test_lastrun_info = {"test": "run"}
        with open(cmd.lastrun_filename, "w") as lastrun:
            return json.dump(test_lastrun_info, lastrun)

        assert cmd.get_lastrun_info() == test_lastrun_info

    def test_update_lastrun_info(self, tmpdir):
        cmd = sync_annotation_export.Command()
        cmd.lastrun_filename = tmpdir / "test_lastrun"
        current_run = datetime.now()
        # does not yet exist
        assert not cmd.lastrun_filename.exists()
        cmd.update_lastrun_info(current_run)

        # last run file should exist now
        assert cmd.lastrun_filename.exists()
        # confirm it has the expected contents
        with open(cmd.lastrun_filename) as lastrun:
            lastrun_info = json.load(lastrun)

        assert lastrun_info[cmd.script_id] == current_run.isoformat()

        # confirm updating preserves other content
        with open(cmd.lastrun_filename, "w") as lastrun:
            return json.dump({"foo": "bar"}, lastrun)
        cmd.update_lastrun_info(current_run)

        # confirm that existing content was not destroyed
        with open(cmd.lastrun_filename) as lastrun:
            lastrun_info = json.load(lastrun)

        assert lastrun_filename["foo"] == "bar"

    def test_script_lastrun(self, tmpdir):
        cmd = sync_annotation_export.Command()
        cmd.lastrun_filename = tmpdir / "test_lastrun"
        # create a mock for export repo
        cmd.anno_exporter = Mock()
        now = timezone.now()

        # should use git log if last run file does not exist
        mocklogref = Mock(time=(now.timestamp(), 0))
        # should use the last (most recent) comment in the log ref
        cmd.anno_exporter.repo.head.reference.log.return_value = [Mock(), mocklogref]
        # last_commit = self.anno_exporter.repo.head.reference.log()[-1]

        script_lastrun = cmd.script_lastrun()
        # should be equivalent to the datetime we used to generate the timestamp
        assert script_lastrun == now

        cmd.anno_exporter.reset_mock()
        # create last run file with our timestamp
        cmd.update_lastrun_info(now)
        # should get that time back
        assert cmd.script_lastrun() == now
        # and should not query git log
        assert cmd.anno_exporter.repo.head.reference.log.call_count == 0

    @pytest.mark.django_db
    @patch(
        "geniza.corpus.management.commands.sync_annotation_export.AnnotationExporter"
    )
    def test_handle_nochange(self, mock_annoexporter, tmpdir):
        remote_git_url = "git:somewhere.co/repo.git"
        with override_settings(
            ANNOTATION_BACKUP_PATH="some/path", ANNOTATION_BACKUP_GITREPO=remote_git_url
        ):

            stdout = StringIO()
            cmd = sync_annotation_export.Command(stdout=stdout)
            cmd.lastrun_filename = tmpdir / "test_lastrun"
            # set lastrun so it won't query git repo
            now = timezone.now()
            cmd.update_lastrun_info(now)
            cmd.handle(verbosity=1)
            # should report 0 entries found
            output = stdout.getvalue()
            assert "0 annotation log entries" in output
            # should init exporter, but not export anything
            assert mock_annoexporter.call_count == 1
            mock_exporter = mock_annoexporter.return_value
            mock_exporter.setup_repo.assert_called()
            assert mock_exporter.export.call_count == 0
            assert mock_exporter.sync_github.call_count == 0

    @pytest.mark.django_db
    @patch(
        "geniza.corpus.management.commands.sync_annotation_export.AnnotationExporter"
    )
    def test_handle_change(self, mock_annoexporter, tmpdir, annotation):
        remote_git_url = "git:somewhere.co/repo.git"
        with override_settings(
            ANNOTATION_BACKUP_PATH="some/path", ANNOTATION_BACKUP_GITREPO=remote_git_url
        ):

            stdout = StringIO()
            cmd = sync_annotation_export.Command(stdout=stdout)
            cmd.lastrun_filename = tmpdir / "test_lastrun"
            # set lastrun before we create a test log entry
            now = timezone.now()
            cmd.update_lastrun_info(now)

            # create a log entry for our fixture annotation
            script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
            annotation_ctype = ContentType.objects.get_for_model(Annotation)

            LogEntry.objects.log_action(
                user_id=script_user.id,
                content_type_id=annotation_ctype.pk,
                object_id=annotation.pk,
                object_repr=repr(annotation),
                action_flag=CHANGE,
            )

            # run the handle method
            cmd.handle(verbosity=1)

            # should report 1 entry found
            output = stdout.getvalue()
            assert "1 annotation log entry" in output
            # should init exporter and export one document
            assert mock_annoexporter.call_count == 1
            mock_exporter = mock_annoexporter.return_value
            mock_exporter.setup_repo.assert_called()
            pgpid = Document.id_from_manifest_uri(annotation.target_source_manifest_id)
            mock_exporter.export.assert_called_with(
                pgpids=[pgpid], modifying_users=set([script_user])
            )
            assert mock_exporter.sync_github.call_count == 1

    @pytest.mark.django_db
    @patch(
        "geniza.corpus.management.commands.sync_annotation_export.AnnotationExporter"
    )
    def test_handle_delete(
        self, mock_annoexporter, tmpdir, annotation, admin_client, admin_user
    ):
        remote_git_url = "git:somewhere.co/repo.git"
        with override_settings(
            ANNOTATION_BACKUP_PATH="some/path", ANNOTATION_BACKUP_GITREPO=remote_git_url
        ):

            stdout = StringIO()
            cmd = sync_annotation_export.Command(stdout=stdout)
            cmd.lastrun_filename = tmpdir / "test_lastrun"
            # set lastrun
            now = timezone.now()

            pgpid = Document.id_from_manifest_uri(annotation.target_source_manifest_id)

            # delete fixeture annotation with DELETE request as admin;
            # this will create a log entry with expected change message
            response = admin_client.delete(annotation.get_absolute_url())

            # run the handle method
            cmd.handle(verbosity=1)

            # should report 1 entry found
            output = stdout.getvalue()
            assert "1 annotation log entry" in output
            # should init exporter and export one document
            assert mock_annoexporter.call_count == 1
            mock_exporter = mock_annoexporter.return_value
            mock_exporter.setup_repo.assert_called()
            doc = Document.from_manifest_uri(annotation.target_source_manifest_id)
            mock_exporter.export.assert_called_with(
                pgpids=[pgpid], modifying_users=set([admin_user])
            )
            assert mock_exporter.sync_github.call_count == 1
