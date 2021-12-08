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
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


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

        self.goitein = Creator.objects.get(last_name="Goitein")

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

        self.stdout.write("STATS SUMMARY")
        for key, value in self.stats.items():
            self.stdout.write(f"\t{key}: {value}")

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
        # Find the source wiht the volume that matches the beginning of the shelfmark for the document
        #   The logic where this is split out is split_goitein_type_text

        goitein_footnotes = doc.footnotes.filter(
            source__authors__last_name="Goitein", source__title_en="typed texts"
        )
        count = goitein_footnotes.count()
        if count > 1:
            self.stdout.write(
                f"There were {count} Goitein footnotes found for PGPID {doc.id}, using the first footnote."
            )

        return goitein_footnotes.first()

    def get_volume(self, shelfmark):
        """Given a shelfmark, get our volume label. This logic was determined in
        migration 0011_split_goitein_typedtexts.py
        """
        if shelfmark.startswith("T-S"):
            volume = shelfmark[0:6]
            volume = "T-S Misc" if volume == "T-S Mi" else volume
        else:
            volume = shelfmark.split(" ")[0]
        return volume

    def get_typed_text_source(self, doc):
        """Get Goiteins typed text volume given the shelfmark"""
        default_source = Source.objects.filter(
            title_en="typed texts", authors__last_name="Goitein", volume=""
        ).first()

        volume = self.get_volume(doc.shelfmark)

        goitein_source = Source.objects.filter(
            title_en="typed texts", authors__last_name="Goitein", volume=volume
        )

        if goitein_source:
            assert goitein_source.count() == 1  # TODO: Remove me
            return goitein_source.first()
        else:
            self.stdout.write(
                f"No goitein source with the volume prefix {volume} was found for PGPID {doc.id}. Providing the default source."
            )
            # TODO: Create new source?
            return default_source

    def parse_goitein_note(self, doc, row):
        base_url = "https://commons.princeton.edu/media/geniza/"
        footnote = self.get_goitein_footnotes(doc)
        if footnote:
            url = base_url + row["link_target"]
            footnote.url = url
        else:
            source = self.get_typed_text_source(doc)
            footnote = Footnote(
                source=source, doc_relation=[Footnote.EDITION], content_object=doc
            )
        return footnote

    def get_or_create_index_card_source(self, doc):
        """Get or create the index card source related to a given document"""
        volume = self.get_volume(doc.shelfmark)
        Source.objects.filter(title="Index Cards", volume=volume)
        if not source:
            source_type = SourceType.objects.get(type="Unpublished")
            source = Source(
                # TODO: title, year, edition, languages?
                url="https://geniza.princeton.edu/indexcards/",
                title="Index Cards",
                volume=volume,
                source_type=source_type,
            )
            source.add(self.goitein)
            source.save()

    def parse_indexcard(self, doc, row):
        url = f"https://geniza.princeton.edu/indexcards/index.php?a=card&id={row['link_target']}"
        # Ensure that footnote with the URL doesn't already exist
        existing_footnote = doc.footnotes.filter(url=url)
        if not existing_footnote:
            source = self.get_or_create_index_card_source(doc)
            return Footnote(
                source=source,
                url=url,
                content_object=doc,
                doc_relation=[Footnote.DISCUSSION],
            )
        else:
            return existing_footnote

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

        # Get new or updated footnote for each link type
        if row["link_type"] == "goitein_note":
            footnote = self.parse_goitein_note(doc, row)
        elif row["link_type"] == "indexcard":
            self.parse_indexcard(doc, row)
        elif row["link_type"] == "jewish-traders":
            self.parse_jewish_traders(doc, row)
        elif row["link_type"] == "india-traders":
            self.parse_india_traders(doc, row)
        else:
            self.stats["skipped"] += 1

        if self.dryrun:
            # Log
            pass
        else:
            pass
            # footnote.save()
