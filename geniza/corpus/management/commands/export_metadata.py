import os
import time
from functools import cached_property

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.utils import timezone
from git import GitCommandError, Repo

from geniza.common.utils import Timer, Timerable
from geniza.corpus.annotation_export import generate_coauthor_commit
from geniza.corpus.management.lastrun_command import LastRunCommand
from geniza.corpus.metadata_export import PublicDocumentExporter, PublicFragmentExporter
from geniza.entities.metadata_export import PublicPersonExporter
from geniza.footnotes.metadata_export import (
    PublicFootnoteExporter,
    PublicSourceExporter,
)


class MetadataExportRepo(Timerable):
    """Utility class with functionality for generating metadata exports
    and commiting to git."""

    local_path_key = "METADATA_BACKUP_PATH"
    remote_url_key = "METADATA_BACKUP_GITREPO"

    repo_dir_data = "data"
    ext_csv = ".csv"

    #: default commit message
    default_commit_msg = "Automated metadata export from PGP"

    exports = {
        "documents": PublicDocumentExporter,
        "fragments": PublicFragmentExporter,
        "sources": PublicSourceExporter,
        "footnotes": PublicFootnoteExporter,
        "people": PublicPersonExporter,
    }

    def __init__(
        self, local_path=None, remote_url=None, print_func=None, progress=True
    ):
        self._local_path = local_path
        self._remote_url = remote_url
        self.print = print_func if print_func is not None else print
        self.progress = progress

        # make sure repo exists and is initialized in directory
        try:
            if not os.path.exists(self.local_path):
                with self.timer("Cloning repository"):
                    Repo.clone_from(url=self.remote_url, to_path=self.local_path)

            # set repo obj
            self.repo = Repo(self.local_path)
        except GitCommandError as e:
            raise CommandError(
                f"Git command failed. Does repository exist?\n\nError message:\n\n{e}"
            )

    @cached_property
    def local_path(self):
        if not (self._local_path or hasattr(settings, self.local_path_key)):
            raise CommandError(
                f"Please set {self.local_path_key} in local_settings.py or settings file."
            )
        return os.path.abspath(
            self._local_path or getattr(settings, self.local_path_key)
        )

    @cached_property
    def remote_url(self):
        if not (self._remote_url or hasattr(settings, self.remote_url_key)):
            raise CommandError(
                f"Please set {self.remote_url_key} in local_settings.py or settings file."
            )
        return self._remote_url or getattr(settings, self.remote_url_key)

    @cached_property
    def path_data(self):
        odir = os.path.join(self.local_path, self.repo_dir_data)
        if not os.path.exists(odir):
            os.makedirs(odir)
        return odir

    def get_path_csv(self, docname):
        "generate export path based on export type"
        return os.path.join(self.path_data, docname + self.ext_csv)

    @cached_property
    def path_documents_csv(self):
        return self.get_path_csv("documents")

    @cached_property
    def path_footnotes_csv(self):
        return self.get_path_csv("footnotes")

    @cached_property
    def path_sources_csv(self):
        return self.get_path_csv("sources")

    @cached_property
    def path_fragments_csv(self):
        return self.get_path_csv("fragments")

    @cached_property
    def path_people_csv(self):
        return self.get_path_csv("people")

    @cached_property
    def paths(self):
        return [
            self.path_documents_csv,
            self.path_footnotes_csv,
            self.path_sources_csv,
            self.path_fragments_csv,
            self.path_people_csv,
        ]

    ############################################
    ## LOCAL EXPORTING
    ############################################

    def export_data(self, lastrun, sync=False):
        "generate all exports"

        # pull any remote changes before making any local modifications
        self.repo_pull()

        # get all log entries since the last run
        log_entries = LogEntry.objects.filter(action_time__gte=lastrun)

        # if there are NO changes, bail out
        if log_entries.count() == 0:
            self.print("No changes since last run")
            return

        # run all configured exports
        for export_name, exporter in self.exports.items():
            with self.timer(f"Exporting { export_name } data"):
                subset_logentries = log_entries.filter(**exporter.content_type_filter)
                # if there are no changes, move to next export
                if not subset_logentries.count():
                    self.print("No changes for %s" % export_name)
                    continue

                export_path = self.get_path_csv(export_name)
                exporter(progress=self.progress).write_export_data_csv(export_path)
            if sync:
                # filter log entries to those for this export
                users = self.get_modifying_users(subset_logentries)
                self.repo_add(export_path)
                self.repo_commit(modifying_users=users, msg=export_name)

        # if sync is requested, push all committed changes
        if sync:
            self.repo_push()

    def get_modifying_users(self, log_entries):
        """Given a :class:`~django.contrib.admin.models.LogEentry` queryset,
        return a :class:`~django.contrib.admin.models.User` queryset
        for the set of users who associated with any of the log entries."""
        return User.objects.exclude(username=settings.SCRIPT_USERNAME).filter(
            username__in=set(
                log_entries.only("user").values_list("user__username", flat=True)
            )
        )

    ############################################
    ## Remote Repo Management
    ############################################

    def repo_origin(self):
        "check if git repository has a remote origin"
        try:
            return self.repo.remote(name="origin")
        except ValueError:
            self.print("No origin repository, unable to push updates")

    def repo_pull(self):
        "pull changes from remote"
        with self.timer("Pulling repository"):
            origin = self.repo_origin()
            if origin:
                origin.pull()

    def repo_add(self, filename=None):
        "add modified files to git"
        files_to_add = [filename] if filename else self.paths
        path = filename or "any changes"
        with self.timer("Adding %s" % path):
            for fn in files_to_add:
                if os.path.exists(fn):
                    self.repo.index.add(fn)

    def repo_commit(self, modifying_users=None, msg=None):
        "commit changes to local git repository"
        if self.repo.is_dirty():  # only commit if there are changes
            commit_msg = self.get_commit_message(modifying_users, msg)
            self.repo.index.commit(commit_msg)

    def get_commit_message(self, modifying_users=None, msg=None):
        """Construct a commit message. Uses the default commit with
        optional addendum specified by `msg` parameter,
        constructs a co-author commit if there are any modifying users,
        and combines with the base commit message."""
        # copied/adapted  from annotation_export
        commit_msg = self.default_commit_msg
        if msg is not None:
            commit_msg = "%s - %s" % (commit_msg, msg)

        if not modifying_users:
            return commit_msg
        return "%s\n\n%s" % (
            commit_msg,
            generate_coauthor_commit(modifying_users),
        )

    def repo_push(self):
        "push changes to remote git repository"
        # push data updates
        with self.timer("Pushing any changes"):
            origin = self.repo_origin()
            if origin:
                origin.push()

    def sync_remote(self):
        "synchronize with remote git repository"
        with self.timer("Syncing metadata into remote repo"):
            # NOTE: can't pull here because it errors if there are
            # unstaged changes
            self.repo_add()
            self.repo_commit()
            self.repo_push()


class Command(LastRunCommand, Timerable):
    # id for this script in the last run file info
    script_id = "metadata-export"

    def print(self, *x, **y):
        """
        A stdout-friendly method of printing for manage.py commands
        """
        if not hasattr(self, "to_print") or self.to_print:
            self.stdout.write(" ".join(str(xx) for xx in x), ending=y.get("end", "\n"))

    def add_arguments(self, parser):
        parser.add_argument(
            "-w",
            "--write",
            action="store_true",
            help="Write export data to local files",
        )
        parser.add_argument(
            "-s",
            "--sync",
            action="store_true",
            help="Sync local files to remote repository",
        )

        parser.add_argument(
            "-p",
            "--path",
            type=str,
            default="",
            required=False,
            help="Set local_path for files",
        )
        parser.add_argument(
            "-u",
            "--url",
            type=str,
            default="",
            required=False,
            help="Set remote_url for repository",
        )

    def handle(self, *args, **options):
        self.to_print = options["verbosity"] >= 2

        mrepo = MetadataExportRepo(
            local_path=options["path"],
            remote_url=options["url"],
            print_func=self.print,
            progress=options["verbosity"] >= 1,
        )
        with self.timer("Getting repository information"):
            self.print(f"Repository local path = {mrepo.local_path}")
            self.print(f"Repository remote url = {mrepo.remote_url}")

        # Write with optional sync
        if options["write"]:
            # determine script last run
            lastrun = self.script_lastrun(mrepo.repo)
            # store the datetime immediately after this query for the next run
            new_lastrun = timezone.now()
            mrepo.export_data(lastrun, sync=options["sync"])
            # when we write and sync, update last run info
            if options["sync"]:
                self.update_lastrun_info(new_lastrun)

        # Sync?
        if options["sync"] and not options["write"]:
            mrepo.sync_remote()

        # should we update last run if we sync changes to default location?
        # if options["sync"] and not options["path"] and not options["url"]:
        # self.update_lastrun_info() # needs new last run arg
