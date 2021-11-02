import os.path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from git import Repo

from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote


class Command(BaseCommand):
    def handle(self, *args, **options):
        # get settings for remote git repository url and local path
        gitrepo_url = settings.TEI_TRANSCRIPTIONS_GITREPO
        gitrepo_path = settings.TEI_TRANSCRIPTIONS_LOCAL_PATH

        # make sure we have latest tei content from git repository
        self.sync_git(gitrepo_url, gitrepo_path)

        # sync tei
        # for each tei file, identify the document and update the transcription
        # iterate through all .xml files in git repo path; base name == pgpid
        # — how to identify corresponding footnote?
        # convert tei to iiif annotation with blocks & line numbers

    def sync_git(self, gitrepo_url, local_path):
        # ensure git repository has been cloned and content is up to date

        # if directory does not yet exist, clone repository
        if not os.path.isdir(local_path):
            self.stdout.write(
                "Cloning TEI transcriptions repository to %s" % local_path
            )
            Repo.clone_from(url=gitrepo_url, to_path=local_path)
        else:
            # pull any changes since the last run
            Repo(local_path).remotes.origin.pull()
