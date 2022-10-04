import json
from datetime import datetime
from unittest.mock import Mock

from django.utils import timezone

from geniza.corpus.management.commands import sync_annotation_export


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
