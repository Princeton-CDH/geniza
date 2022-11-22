import json
import os.path
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone


class LastRunCommand(BaseCommand):
    """Base command class with common behavior for tracking and updating
    last run.  Extending classes should set a unique script id,
    and call :meth:`update_lastrun_info` after successful completion."""

    # filename for last run information (stored in current user's home)
    lastrun_filename = os.path.join(os.path.expanduser("~"), ".pgp_export_lastrun")
    # id for this script in the last run file info
    script_id = None

    #: default verbosity
    v_normal = 1

    def get_lastrun_info(self):
        # check for information about the last run of this script;
        # load as json if it is exists
        if os.path.exists(self.lastrun_filename):
            with open(self.lastrun_filename) as lastrun:
                # load and parse as json
                return json.load(lastrun)

    def update_lastrun_info(self, new_lastrun):
        # Update or create last run information file
        lastrun_info = self.get_lastrun_info() or {}
        lastrun_info.update({self.script_id: new_lastrun.isoformat()})
        with open(self.lastrun_filename, "w") as lastrun:
            return json.dump(lastrun_info, lastrun, indent=2)

    def script_lastrun(self, repo):
        # determine the datetime for the last run of this script;
        # must pass in git repo object for fallback time

        # load information about the last run of this script
        lastrun_data = self.get_lastrun_info()
        # if the file exists, pull out modified value for this scriptdi
        if lastrun_data and self.script_id in lastrun_data:
            return datetime.fromisoformat(lastrun_data[self.script_id])

        # if lastrun file is not found, use last git commit on the repository
        # (potentially unreliable if non-data repo content is updated
        # and lastrun file does not exist, but should be ok.)

        # get the most recent commit on the head of the current branch
        last_commit = repo.head.reference.log()[-1]
        # log ref entry time attribute is a tuple;
        # first portion is int time, second portion is timezone offset;
        # according to docs, time.altzone is only in effect during DST;
        # unclear how to incorporate into datetime object!

        # convert to a datetime object
        return timezone.make_aware(datetime.fromtimestamp(last_commit.time[0]))
