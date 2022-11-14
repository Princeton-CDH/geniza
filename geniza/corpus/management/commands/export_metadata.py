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
    local_path_key = "METADATA_REPO_LOCAL_PATH"
    remote_url_key = "METADATA_REPO_REMOTE_URL"

    repo_dir_data = "data"
    ext_csv = ".csv"

    def __init__(self, local_path=None, remote_url=None, print_func=None):
        self._local_path = local_path
        self._remote_url = remote_url
        self.print = print_func if print_func is not None else print

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

    def add_and_commit(self):
        for fn in self.paths:
            if os.path.exists(fn):
                self.repo.index.add(fn)
        self.repo.index.commit(
            "Auto-syncing @ " + timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def write_local(self):
        # write docs

        with self.timer("Exporting document objects"):
            PublicDocumentExporter(progress=True).to_csv(self.path_documents_csv)

        # write sources
        with self.timer("Exporting source objects"):
            SourceExporter(progress=True).to_csv(self.path_sources_csv)

        # write footnotes
        with self.timer("Exporting footnote objects"):
            FootnoteExporter(progress=True).to_csv(self.path_footnotes_csv)

    def sync_remote(self):
        """Sync local repository content with origin repository. Assumes
        :meth:`setup_repo` has already been run, and any new or modified
        files have been committed."""
        try:
            with self.timer("Pulling repository"):
                origin = self.repo.remote(name="origin")
                # pull any remote changes since our last commit
                origin.pull()

            # commit?
            with self.timer("Adding any changes"):
                self.add_and_commit()

            # push data updates
            with self.timer("Pushing any changes"):
                result = origin.push()
                if result:
                    info = result[0]
                    self.print(f"Result = {info.flags}")
        except ValueError:
            self.print("No origin repository, unable to push updates")


class Command(BaseCommand, Timerable):
    def print(self, *x, **y):
        """
        A stdout-friendly method of printing for manage.py commands
        """
        end = y.get("end", "\n")
        self.stdout.write(" ".join(str(xx) for xx in x), ending=end)

    def add_arguments(self, parser):
        parser.add_argument("-w", "--write", action="store_true")
        parser.add_argument("-s", "--sync", action="store_true")

        parser.add_argument("-p", "--path", type=str, default="", required=False)
        parser.add_argument("-u", "--url", type=str, default="", required=False)

    def handle(self, *args, **options):
        # get
        mrepo = MetadataExportRepo(
            local_path=options["path"], remote_url=options["url"], print_func=self.print
        )
        with self.timer("Getting repository information"):
            self.print(f"Repository local path = {mrepo.local_path}")
            self.print(f"Repository remote url = {mrepo.remote_url}")

        # Write
        if options["write"]:
            with self.timer("Rewriting metadata into local path"):
                mrepo.write_local()

        # Sync?
        if options["sync"]:
            with self.timer("Syncing metadata into remote repo"):
                mrepo.sync_remote()
