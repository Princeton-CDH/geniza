import csv
import re
from collections import Counter

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from parasolr.django.signals import IndexableSignalHandler

from geniza.corpus.models import Document
from geniza.footnotes.models import Creator


class Command(BaseCommand):
    """Takes a CSV export of the Geniza v3 database to add footnotes with Goitein
    and Jewish / Indian trader links. Expects the following CSV headers:
    linkID object_id link_type link_title link_target link_attribution
    """

    help = __doc__

    def __init__(self, *args, **options):
        super().__init__(*args, **options)

        self.stats = Counter()
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.expected_headers = [
            "linkID",
            "object_id",
            "link_type",
            "link_title",
            "link_target",
            "link_attribution",
        ]
        self.skipped_types = ["image", "iiif", "transcription", "cudl"]

        # Get Goitein and sources
        self.goitein = Creator.objects.get(last_name="Goitein")
        self.goitein_sources = self.goitein.source_set.all()

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)
        parser.add_argument("-t", "--link_type")
        parser.add_argument("-o", "--overwrite", action="store_true")
        parser.add_argument("-d", "--dryrun", action="store_true")

    def handle(self, *args, **options):
        self.csv_path = options.get("csv")
        self.overwrite = options.get("overwrite")
        self.dryrun = options.get("dryrun")
        self.link_type = options.get("link_type")

        try:
            with open(self.csv_path) as f:
                csvreader = csv.DictReader(f)
                for row in csvreader:
                    if not all([header in row for header in self.expected_headers]):
                        raise CommandError(
                            f"CSV must include the following headers: {self.expected_headers}"
                        )
                    self.add_link(row)
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {self.csv_path}")

        self.stdout.write(f"Documents not found: {self.stats['document_not_found']}")

    def get_document(self, pgpid: int):
        """Find a document given its new or old PGPID"""
        pgpid = int(pgpid)
        try:
            return Document.objects.get(
                models.Q(id=pgpid) | models.Q(old_pgpids__contains=[pgpid])
            )
        except Document.DoesNotExist:
            self.stats["document_not_found"] += 1
            self.stdout.write("Document %s not found in database" % pgpid)
            return

    def get_goitein_footnotes(self, doc):
        # TODO: How to handle multiple Goitein footnotes?
        goitein_footnotes = doc.footnotes.filter(source__in=self.goitein_sources)
        count = goitein_footnotes.count()
        if count > 1:
            self.stdout.write(
                f"There were {count} Goitein footnotes found for PGPID {doc.id}, using the first footnote."
            )
        elif not count:
            # ?: Should a new footnote be created if there's not already a Goitein footnote?
            self.stdout.write(
                f"No Goitein footnote found for PGPID {doc.id}. A url will not be added."
            )

        return goitein_footnotes.first()

    def parse_goitein_note(self, doc, row):
        base_url = "https://commons.princeton.edu/media/geniza/"
        footnote = self.get_goitein_footnotes(doc)
        if footnote:
            url = base_url + row["link_target"]
            footnote.url = url
            self.stats["url_updated"] += 1
            # log_message.append("updated URL")
            if self.dryrun:
                self.stdout.write(f"Set footnote url for PGPID {doc.id} to {url}")
            else:
                # footnote.save()
                # ?: Only the footnote needs to be saved, correct?
                # LOG CHANGES
                pass

    def parse_indexcard(self, doc, row):
        pass

    def parse_jewish_traders(self, doc, row):
        pass

    def parse_india_traders(self, doc, row):
        pass

    def add_link(self, row):
        if (self.link_type and self.link_type != row["link_type"]) or (
            row["link_type"] in self.skipped_types
        ):
            return

        doc = self.get_document(row["object_id"])
        if not doc:
            return

        # Process document link
        # Create new footnote
        # If dryrun, write process to stdout
        # Else save and log

        if row["link_type"] == "goitein_note":
            self.parse_goitein_note(doc, row)
        elif row["link_type"] == "indexcard":
            self.parse_indexcard(doc, row)
        elif row["link_type"] == "jewish-traders":
            self.parse_jewish_traders(doc, row)
        elif row["link_type"] == "india-traders":
            self.parse_india_traders(doc, row)
        else:
            self.stats["skipped"] += 1
