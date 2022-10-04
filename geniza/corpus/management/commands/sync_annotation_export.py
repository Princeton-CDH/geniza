import json
import os.path
from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils import timezone

from geniza.annotations.models import Annotation
from geniza.corpus.annotation_export import AnnotationExporter
from geniza.corpus.models import Document


class Command(BaseCommand):
    """Synchronize annotation backup data with GitHub"""

    # filename for last run information (stored in current user's home)
    lastrun_filename = os.path.join(os.path.expanduser("~"), ".pgp_export_lastrun")
    # id for this script in the last run file info
    script_id = "annotations"

    #: default verbosity
    v_normal = 1

    def handle(self, *args, **options):
        if not getattr(settings, "ANNOTATION_BACKUP_PATH"):
            raise CommandError(
                "Please configure ANNOTATION_BACKUP_PATH in django settings"
            )

        # initialize annotation exporter; don't push changes automatically
        self.anno_exporter = AnnotationExporter(
            stdout=self.stdout, verbosity=options["verbosity"], push_changes=False
        )
        # set up repo object and pull any changes
        self.anno_exporter.setup_repo()

        # determine last run
        lastrun = self.script_lastrun()
        # get annotation log entries since the last run
        annotation_ctype = ContentType.objects.get_for_model(Annotation)
        # get all log entries for changes on annotations since the last run
        log_entries = LogEntry.objects.filter(
            content_type_id=annotation_ctype.pk, action_time__gte=lastrun
        )
        # store the datetime immediately after this query for the next run
        new_lastrun = timezone.now()

        if options["verbosity"] >= self.v_normal:
            print("%d annotation log entries since %s" % (log_entries.count(), lastrun))

        # generate exports based on what has been changed
        if log_entries.exists():

            # TODO: handle deletions (object no longer in db)

            # make a dictionary of modified annotations and the users who modified them
            modified_annotations = defaultdict(list)
            for log_entry in log_entries:
                modified_annotations[log_entry.object_id].append(log_entry.user)

            # load the modified annotations from the database
            annotations = Annotation.objects.filter(
                id__in=list(modified_annotations.keys())
            )
            # group by manifest, so we can export by document
            annos_by_manifest = annotations.group_by_manifest()

            for manifest, annotations in annos_by_manifest.items():
                # export transcription for the specified document,
                # documenting the users who modified it
                document = Document.from_manifest_uri(manifest)

                # collect all users who modified any of the annotations
                # for this document based on the collected log entries
                users = set()
                for anno in annotations:
                    # NOTE: annotation id is a uuid; must cast to string
                    # for dict lookup to succeeed
                    users |= set(modified_annotations[str(anno.id)])

                self.anno_exporter.export(
                    pgpids=[document.pk],
                    modifying_users=users,
                )

            # push changes to remote
            self.anno_exporter.sync_github()

        # update the last run for the next time
        self.update_lastrun_info(new_lastrun)

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

    def script_lastrun(self):
        # determine the datetime for the last run of this script

        # load information about the last run of this script
        lastrun_data = self.get_lastrun_info()
        # if the file exists, pull out modified value for this scriptdi
        if lastrun_data and self.script_id in lastrun_data:
            return datetime.fromisoformat(lastrun_data[self.script_id])

        # if lastrun file is not found, use last git commit on the repository
        # (potentially unreliable if non-data repo content is updated
        # and lastrun file does not exist, but should be ok.)

        # get the most recent commit on the head of the current branch
        last_commit = self.anno_exporter.repo.head.reference.log()[-1]
        # log ref entry time attribute is a tuple;
        # first portion is int time, second portion is timezone offset;
        # according to docs, time.altzone is only in effect during DST;
        # unclear how to incorporate into datetime object!

        # convert to a datetime object
        return timezone.make_aware(datetime.fromtimestamp(last_commit.time[0]))
