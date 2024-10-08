import json
import os.path
from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import CommandError
from django.template.defaultfilters import pluralize
from django.utils import timezone

from geniza.annotations.models import Annotation
from geniza.corpus.annotation_export import AnnotationExporter
from geniza.corpus.annotation_utils import document_id_from_manifest_uri
from geniza.corpus.management.lastrun_command import LastRunCommand


class Command(LastRunCommand):
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
        lastrun = self.script_lastrun(self.anno_exporter.repo)
        # get annotation log entries since the last run
        annotation_ctype = ContentType.objects.get_for_model(Annotation)
        # get all log entries for changes on annotations since the last run
        log_entries = LogEntry.objects.filter(
            content_type_id=annotation_ctype.pk, action_time__gte=lastrun
        )
        # store the datetime immediately after this query for the next run
        new_lastrun = timezone.now()

        if options["verbosity"] >= self.v_normal:
            log_entry_count = log_entries.count()
            self.stdout.write(
                "%d annotation log entr%s since %s"
                % (
                    log_entry_count,
                    pluralize(log_entry_count, "y,ies"),
                    lastrun,
                )
            )

        # generate exports based on what has been changed
        if log_entries.exists():

            # make a dictionary of annotations and the users who modified them
            modified_annotations = defaultdict(list)
            # also track any deletions
            # needs special handling since annotation is no longer in db
            deletions = []

            for log_entry in log_entries:
                modified_annotations[log_entry.object_id].append(log_entry.user)
                if log_entry.action_flag == DELETION:
                    deletions.append(log_entry)

            # load modified annotations from the database
            annotations = Annotation.objects.filter(
                id__in=list(modified_annotations.keys())
            )
            # group by manifest, so we can export by document
            annos_by_manifest = annotations.group_by_manifest()

            # special case: deleted annotations don't exist in the db,
            # but the transcription should be re-exported to reflect removal
            manifest_deletions = []  # track manifests with deletions
            for log_entry in deletions:
                # if modified via annotation delete view, change message
                # should include manifest uri
                manifest_uri = json.loads(log_entry.change_message).get("manifest_uri")
                if manifest_uri:
                    # add an unsaved annotation with the proper id to the dict
                    annos_by_manifest[manifest_uri].append(
                        Annotation(id=log_entry.object_id)
                    )
                    manifest_deletions.append(manifest_uri)

            for manifest, annotations in annos_by_manifest.items():
                # export transcription for the specified document,
                # documenting the users who modified it
                document_id = document_id_from_manifest_uri(manifest)

                # collect all users who modified any of the annotations
                # for this document based on the collected log entries
                users = set()
                for anno in annotations:
                    # NOTE: annotation id is a uuid; must cast to string
                    # for dict lookup to succeeed
                    users |= set(modified_annotations[str(anno.id)])

                exported = self.anno_exporter.export(
                    pgpids=[document_id],
                    modifying_users=users,
                    commit_msg="%s - PGPID %d"
                    % (AnnotationExporter.default_commit_msg, document_id),
                )
                # special case: if annotation has been deleted AND
                # corresponding document has been deleted
                if not exported and manifest in manifest_deletions:
                    self.anno_exporter.cleanup(
                        document_id,
                        modifying_users=users,
                        commit_msg="%s - removing files for PGPID %d"
                        % (AnnotationExporter.default_commit_msg, document_id),
                    )

            # push changes to remote
            self.anno_exporter.sync_github()

        # update the last run for the next time
        self.update_lastrun_info(new_lastrun)
