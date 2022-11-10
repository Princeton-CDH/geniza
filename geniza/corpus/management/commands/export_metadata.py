import os
import time
from functools import cached_property

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from git import GitCommandError, Repo

from geniza.corpus.metadata_export import PublicDocumentExporter


class MetadataExportRepo:
    local_path_key = "METADATA_REPO_LOCAL_PATH"
    remote_url_key = "METADATA_REPO_REMOTE_URL"

    repo_dir_data = "data"
    ext_csv = ".csv"

    def __init__(self, local_path=None, remote_url=None):
        self._local_path = local_path
        self._remote_url = remote_url

        # make sure repo exists and is initialized in directory
        try:
            if not os.path.exists(self.local_path):
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
        self.repo.index.add(odir)
        return odir

    @cached_property
    def path_documents_csv(self):
        ofn = os.path.join(self.path_data, "documents" + self.ext_csv)
        self.repo.index.add(ofn)
        return ofn

    def write_local(self):
        # write docs
        pde = PublicDocumentExporter(progress=True)
        pde.write_export_data_csv(self.path_documents_csv)

        # write sources
        # ...

    def sync_remote(self):
        """Sync local repository content with origin repository. Assumes
        :meth:`setup_repo` has already been run, and any new or modified
        files have been committed."""
        try:
            origin = self.repo.remote(name="origin")
            # pull any remote changes since our last commit
            origin.pull()

            # commit?
            self.repo.index.commit(
                "Auto-syncing @ " + timezone.now().strftime("%Y%m%dT%H%M%S")
            )

            # push data updates
            result = origin.push()
        except ValueError:
            print("No origin repository, unable to push updates")


class Command(BaseCommand):
    def print(self, *x, **y):
        """
        A stdout-friendly method of printing for manage.py commands
        """
        self.stdout.write(" ".join(str(xx) for xx in x), ending="\n", **y)

    def add_arguments(self, parser):
        parser.add_argument("-w", "--write", action="store_true")
        parser.add_argument("-s", "--sync", action="store_true")

        parser.add_argument("-p", "--path", type=str, default="", required=False)
        parser.add_argument("-u", "--url", type=str, default="", required=False)

    def handle(self, *args, **options):
        # get
        mrepo = MetadataExportRepo(
            local_path=options["path"], remote_url=options["url"]
        )
        self.print(f"Repository local path = {mrepo.local_path}")
        self.print(f"Repository remote url = {mrepo.remote_url}")

        # Write
        if options["write"]:
            self.print("\nRewriting metadata into local path ...")
            mrepo.write_local()

        # Sync?
        if options["sync"]:
            self.print("\nSyncing metadata into remote repo ...")
            mrepo.sync_remote()
