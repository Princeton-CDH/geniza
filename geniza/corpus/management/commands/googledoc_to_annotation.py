"""
Script to convert translation content from Google Docs template
to IIIF annotations in the configured annotation server.

Adapted from tei_to_annotation management command.
"""

import io
import os.path
import unicodedata
from collections import defaultdict

from addict import Dict
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.models import User
from django.template.defaultfilters import pluralize
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from parasolr.django.signals import IndexableSignalHandler
from rich.progress import MofNCompleteColumn, Progress

from geniza.annotations.models import Annotation
from geniza.corpus.annotation_export import AnnotationExporter
from geniza.corpus.management.commands import tei_to_annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source


class Command(tei_to_annotation.Command):
    """Synchronize Google Doc translations to digital translation footnote content"""

    v_normal = 1  # default verbosity

    normalized_unicode = set()

    document_not_found = []

    source_not_found = []

    REMOVE_ATTRIBUTES = ["style", "class"]  # attributes to strip from html elements

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_id",
            help="The ID of the Google Drive folder containing translation documents.",
        )

    def handle(self, *args, **options):
        self.verbosity = options["verbosity"]
        self.stats = defaultdict(int)
        self.stats["files"] = 0
        self.stats["created"] = 0
        self.script_run_start = timezone.now()

        # get script user for log entries
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # get drive id from settings
        self.drive_id = settings.GOOGLE_DRIVE_ID

        # get folder id from provided args
        self.folder_id = options["folder_id"]

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()

        # initialize annotation exporter; don't push changes until the end
        self.anno_exporter = AnnotationExporter(
            stdout=self.stdout,
            verbosity=options["verbosity"],
            push_changes=False,
            # this will be overwritten
            commit_msg="PGP translation export from Google Docs migration",
        )
        self.anno_exporter.setup_repo()

        # use rich progressbar without context manager
        progress = Progress(
            MofNCompleteColumn(), *Progress.get_default_columns(), expand=True
        )
        progress.start()
        fetch_task = progress.add_task("Fetching list of files...", total=None)
        files = []

        try:
            # create drive api client
            self.service = build("drive", "v3", credentials=self.get_credentials())
            page_token = None
            # loop through all pages until there are no more new pages
            while True:
                # find all files in the folder folder_id and drive drive_id
                response = (
                    self.service.files()
                    .list(
                        q=f"'{self.folder_id}' in parents",
                        driveId=self.drive_id,
                        includeItemsFromAllDrives=True,
                        corpora="drive",
                        supportsAllDrives=True,
                        pageToken=page_token,
                    )
                    .execute()
                )
                # add files to list
                files += response.get("files", [])
                # go to the next page if there's a next page token, otherwise end the loop
                page_token = response.get("nextPageToken", None)
                if page_token is None:
                    break

            n = len(files)
            progress.update(
                fetch_task, completed=n, total=n, description=f"Found {n} files."
            )

            # loop through each file, and process it
            process_task = progress.add_task(f"Processing...", total=n)
            for file in response.get("files", []):
                if self.verbosity > self.v_normal:
                    print(f"Processing {file.get('name')}")
                self.stats["files"] += 1
                html_file = self.download_as_html(file.get("id"))
                self.process_file(html_file)
                progress.update(process_task, advance=1, update=True)

        except HttpError as error:
            self.style.ERROR(f"An error occurred: {error}")

        progress.refresh()
        progress.stop()

        print(
            "Processed %(files)d Google Doc(s). \nCreated %(created)d annotation(s)."
            % self.stats
        )

        # push all changes from migration to github
        self.anno_exporter.sync_github()

        # report on missing sources
        if self.source_not_found:
            print(
                "Could not find footnotes for %s document%s:"
                % (len(self.source_not_found), pluralize(self.source_not_found))
            )
            for source in self.source_not_found:
                print("\t%s" % source)

        # report on unicode normalization
        if self.normalized_unicode:
            print(
                "Normalized unicode for %s document%s:"
                % (len(self.normalized_unicode), pluralize(self.normalized_unicode))
            )
            for doc in self.normalized_unicode:
                print("\t%s" % doc)

        if self.document_not_found:
            print(
                "Document not found for %s PGPID%s:"
                % (len(self.document_not_found), pluralize(self.document_not_found))
            )
            for doc in self.document_not_found:
                print("\t%s" % doc)

    def get_credentials(self):
        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
        creds = None
        # The token json file stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(settings.GOOGLE_API_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(
                settings.GOOGLE_API_TOKEN_FILE, SCOPES
            )
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GOOGLE_API_SECRETS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(settings.GOOGLE_API_TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
        return creds

    def download_as_html(self, file_id):
        # export file to HTML
        request = self.service.files().export_media(
            fileId=file_id, mimeType="text/html"
        )
        file = io.BytesIO()

        # start the download, then loop through all chunks until file is downloaded
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()

        return file.getvalue()

    def new_translation_annotation(self):
        # initialize a new annotation dict object with all the defaults set

        anno = Dict()
        setattr(anno, "@context", "http://www.w3.org/ns/anno.jsonld")
        anno.type = "Annotation"
        anno.body = [Dict()]
        anno.body[0].type = "TextualBody"
        anno.body[0].format = "text/html"
        # supplement rather than painting over the image
        # add translating as secondary motivation
        anno.motivation = ["sc:supplementing", "translating"]

        anno.target.source.type = "Canvas"
        anno.target.selector.type = "FragmentSelector"
        anno.target.selector.conformsTo = "http://www.w3.org/TR/media-frags/"

        return anno

    def process_file(self, html_file):
        soup = BeautifulSoup(html_file, "html.parser")
        # first table is metadata, second table is translation
        tables = soup.find_all("table")
        # extract the footnote metadata
        metadata = tables[0].find_all("td")
        # handle earlier and later template revisions
        if len(metadata) == 6:
            # missing notes field; was labeled "Notes" but used for location
            notes = None
            (pgpid, source_id, location) = (td.get_text() for td in metadata[3:])
        elif len(metadata) == 8:
            # includes both Location and Notes fields
            (pgpid, source_id, location, notes) = (td.get_text() for td in metadata[4:])

        # get the document
        try:
            doc = Document.objects.get(pk=int(pgpid))
        except Document.DoesNotExist:
            print(
                self.style.WARNING("Document not found for PGPID %s; skipping" % pgpid)
            )
            self.document_not_found.append(pgpid)
            return

        # get the source
        try:
            source = Source.objects.get(pk=int(source_id))
        except Source.DoesNotExist:
            print(
                self.style.WARNING(
                    f"Source not found for Source ID {source_id} (on PGPID {pgpid}); skipping"
                )
            )
            self.source_not_found.append(source_id)
            return

        # get the first canvas only; researchers want all translation content on first img
        canvas_base_uri = doc.manifest_uri.replace("manifest", "canvas")
        iiif_canvas = next(
            iter(doc.iiif_images(filter_side=True)),
            f"{canvas_base_uri}1/",  # default in case there are no images
        )

        # get or create a digital translation footnote
        (footnote, created) = Footnote.objects.get_or_create(
            object_id=doc.pk,
            content_type=self.get_content_type(doc),
            source=source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        footnote.location = location
        footnote.notes = notes or ""
        footnote.save()
        # log creation
        if created:
            self.log_addition(
                footnote,
                "Created new footnote for migrated Google Docs digital translation",
            )
        else:
            # remove all existing annotations associated with this
            # document and footnote so we can reimport as needed
            existing_annos = Annotation.objects.filter(
                footnote=footnote,
                created__lt=self.script_run_start,
            )
            if existing_annos:
                print(
                    "Removing %s pre-existing annotation%s for %s on %s "
                    % (
                        len(existing_annos),
                        pluralize(existing_annos),
                        footnote.source,
                        doc.pk,
                    )
                )
                # not creating log entries for deletion, but
                # this should probably only come up in dev runs
                existing_annos.delete()

        # extract, process, and create annotations from the translation blocks
        translation = tables[1]
        tds = translation.find_all("td")

        # loop through blocks: each 2-column row is a block, first 2 cells are headers
        blocks = (len(tds) - 2) / 2
        for i in range(int(blocks)):
            # new row every 2 cells; starts at cell 3 because first 2 cells are column headers
            row_start = (i * 2) + 2
            # extract the annotation block label (first column)
            block_label = tds[row_start].get_text()
            # extract the translation (second column)
            translation_cell = tds[row_start + 1]
            # first, process and cleanup all the tags
            for tag in translation_cell.descendants:
                try:
                    # remove unneeded attributes
                    tag.attrs = {
                        key: value
                        for (key, value) in tag.attrs.items()
                        if key not in self.REMOVE_ATTRIBUTES
                    }
                    # remove unnecessary spans that Google Docs adds to each li
                    for span in tag.find_all("span"):
                        span.unwrap()
                    # clear out any unneeded newlines exposed by the previous step
                    tag.smooth()
                except AttributeError:
                    # 'NavigableString' object has no attribute 'attrs'; fine to ignore
                    pass
            html = "\n".join([str(tag) for tag in translation_cell.contents])

            # create an annotation
            anno = self.new_translation_annotation()

            # place on the first canvas
            anno.target.source.id = iiif_canvas
            # apply to the full canvas using % notation
            # (using nearly full canvas to make it easier to edit zones)
            anno.target.selector.value = "xywh=percent:1,1,98,98"

            # add html and optional label to annotation text body
            if not unicodedata.is_normalized("NFC", html):
                self.normalized_unicode.add(pgpid)
                html = unicodedata.normalize("NFC", html)
            anno.body[0].value = html

            # check if label text requires normalization
            if not unicodedata.is_normalized("NFC", block_label):
                self.normalized_unicode.add(pgpid)
                block_label = unicodedata.normalize("NFC", block_label)
            # add label to annotation
            anno.body[0].label = block_label

            # order according to block number
            anno["schema:position"] = i + 1

            # create database annotation
            db_anno = Annotation()
            db_anno.set_content(dict(anno))
            # link to digital translation footnote
            db_anno.footnote = footnote
            db_anno.save()
            # log entry to document annotation creation
            self.log_addition(db_anno, "Migrated from Google Doc translation")

            self.stats["created"] += 1

        # export html/txt translation files to github backup
        self.anno_exporter.export(
            pgpids=[doc.pk],
            commit_msg="Translation migrated from Google Doc - PGPID %d" % doc.pk,
        )