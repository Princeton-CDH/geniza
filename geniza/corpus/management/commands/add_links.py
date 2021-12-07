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

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)
        parser.add_argument("-o", "--overwrite", action="store_true")
        parser.add_argument("-d", "--dryrun", action="store_true")

    def handle(self, *args, **options):
        self.csv_path = options.get("csv")
        self.overwrite = options.get("overwrite")
        self.dryrun = options.get("dryrun")

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

    def parse_goitein_note(self, row):
        base_url = "https://commons.princeton.edu/media/geniza/"
        link = base_url + row["link_target"]

    def parse_indexcard(self, row):
        pass

    def parse_jewish_traders(self, row):
        pass

    def parse_india_traders(self, row):
        pass

    def add_link(self, row):
        if row["link_type"] in self.skipped_types:
            return

        document = self.get_document(row["object_id"])
        if not document:
            return

        # Process document link
        # Create new footnote
        # If dryrun, write process to stdout
        # Else save and log

        if row["link_type"] == "goitein_note":
            self.parse_goitein_note(row)
        elif row["link_type"] == "indexcard":
            self.parse_indexcard(row)
        elif row["link_type"] == "jewish-traders":
            self.parse_jewish_traders(row)
        elif row["link_type"] == "india-traders":
            self.parse_india_traders(row)
        else:
            self.stats["skipped"] += 1
