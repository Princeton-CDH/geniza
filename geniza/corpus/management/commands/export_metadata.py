import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from git import Repo

from geniza.corpus.metadata_export import PublicDocumentExporter


class MetadataExportRepo:
    local_path_settings_key = "METADATA_REPO_LOCAL_PATH"
    remote_url_settings_key = "METADATA_REPO_REMOTE_URL"
    default_remote_url_org = "https://github.com/Princeton-CDH"

    repo_name = "test-geniza-metadata"
    repo_dir_data = "data"
    ext_csv = ".csv"

    def __init__(self, local_path=None, remote_url=None):
        # init vars
        self._local_path = local_path
        self._remote_url = remote_url
        self._repo = None

        # make sure repo exists and is initialized in directory
        if not os.path.exists(self.local_path):
            Repo.clone_from(url=self.remote_url, to_path=self.local_path)

        # set repo obj
        self.repo = Repo(self.local_path)

    @property
    def local_path(self):
        if not self._local_path:
            if hasattr(settings, self.local_path_settings_key):
                self._local_path = getattr(settings, self.local_path_settings_key)
            else:
                self._local_path = os.path.abspath(
                    os.path.join(settings.BASE_DIR, "..", self.repo_name)
                )
        return self._local_path

    @property
    def remote_url(self):
        if not self._remote_url:
            if hasattr(settings, self.remote_url_settings_key):
                self._remote_url = getattr(settings, self.remote_url_settings_key)
            else:
                self._remote_url = os.path.join(
                    self.default_remote_url_org, self.repo_name
                )
        return self._remote_url

    def sync_repo(self):
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

    @property
    def path_data(self):
        odir = os.path.join(self.local_path, self.repo_dir_data)
        if not os.path.exists(odir):
            os.makedirs(odir)
        self.repo.index.add(odir)
        return odir

    @property
    def path_documents_csv(self):
        ofn = os.path.join(self.path_data, "documents" + self.ext_csv)
        self.repo.index.add(ofn)
        return ofn

    def write_metadata(self):
        # write docs
        pde = PublicDocumentExporter(progress=True)
        pde.write_export_data_csv(self.path_documents_csv)

        # write sources

    def sync(self):
        print("Writing metadata")
        self.write_metadata()

        print("Syncing to github")
        self.sync_repo()


class Command(BaseCommand):
    def print(self, *x, **y):
        """
        A stdout-friendly method of printing for manage.py commands
        """
        self.stdout.write(" ".join(str(xx) for xx in x), ending="\n", **y)

    # def add_arguments(self, parser):
    #     ofn = f'pgp_documents-{timezone.now().strftime("%Y%m%dT%H%M%S")}.csv'
    #     parser.add_argument(
    #         "-o", "--output_filename", type=str, default=ofn, required=False
    #     )

    # def handle(self, *args, **options):
    #     began = time.time()
    #     ofn = options["output_filename"]
    #     self.print(f"Exporting data as CSV to: {ofn}")

    #     # exporter = DocumentExporter(progress=True)
    #     # exporter.write_export_data_csv(fn=ofn)
    #     mrepo = MetadataRepo()

    #     self.print(f"Finished CSV export in {time.time()-began:.1f} seconds")

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
            mrepo.write_metadata()

        # Sync?
        if options["sync"]:
            self.print("\nSyncing metadata into remote repo ...")
            mrepo.sync_repo()
