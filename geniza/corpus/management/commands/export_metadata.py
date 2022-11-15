import os
import time
from functools import cached_property

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from git import GitCommandError, Repo

from geniza.common.utils import Timer, Timerable
from geniza.corpus.metadata_export import PublicDocumentExporter
from geniza.footnotes.metadata_export import FootnoteExporter, SourceExporter


class MetadataExportRepo(Timerable):
    local_path_key = "METADATA_BACKUP_PATH"
    remote_url_key = "METADATA_BACKUP_GITREPO"

    repo_dir_data = "data"
    ext_csv = ".csv"

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
    def paths(self):
        return [
            self.path_documents_csv,
            self.path_footnotes_csv,
            self.path_sources_csv,
            self.path_fragments_csv,
        ]

    ############################################
    ## LOCAL EXPORTING
    ############################################

    def export_data(self):
        with self.timer("Exporting metadata into local path"):
            # make sure to pull first
            self.repo_pull()

            # write docs
            with self.timer("Exporting document objects"):
                PublicDocumentExporter(progress=self.progress).write_export_data_csv(
                    self.path_documents_csv
                )

            # write sources
            with self.timer("Exporting source objects"):
                SourceExporter(progress=self.progress).write_export_data_csv(
                    self.path_sources_csv
                )

            # write footnotes
            with self.timer("Exporting footnote objects"):
                FootnoteExporter(progress=self.progress).write_export_data_csv(
                    self.path_footnotes_csv
                )

    ############################################
    ## Remote Repo Management
    ############################################

    def repo_origin(self):
        try:
            return self.repo.remote(name="origin")
        except ValueError:
            self.print("No origin repository, unable to push updates")

    def repo_pull(self):
        with self.timer("Pulling repository"):
            origin = self.repo_origin()
            if origin:
                origin.pull()

    def repo_add(self):
        with self.timer("Adding any changes"):
            for fn in self.paths:
                if os.path.exists(fn):
                    self.repo.index.add(fn)

    def repo_commit(self):
        self.repo.index.commit(
            "Auto-syncing @ " + timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def repo_push(self):
        # push data updates
        with self.timer("Pushing any changes"):
            origin = self.repo_origin()
            if origin:
                origin.push()

    def sync_remote(self):
        with self.timer("Syncing metadata into remote repo"):
            self.repo_pull()
            self.repo_add()
            self.repo_commit()
            self.repo_push()


class Command(BaseCommand, Timerable):
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

        # Write
        if options["write"]:
            mrepo.export_data()

        # Sync?
        if options["sync"]:
            mrepo.sync_remote()
