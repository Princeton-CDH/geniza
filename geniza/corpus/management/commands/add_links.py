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

# TODO: Not all headers are required, look back later and remove unnecessary requirements


class Command(BaseCommand):
    """Takes a CSV export of the Geniza v3 database to add footnotes with Goitein
    and Jewish / Indian trader links. Expects the following CSV headers:
    linkID object_id link_type link_title link_target link_attribution
    """

    help = __doc__

    expected_headers = [
        "linkID",
        "object_id",
        "link_type",
        "link_title",
        "link_target",
        "link_attribution",
    ]
    skipped_types = ["image", "iiif", "transcription", "cudl"]

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)
        parser.add_argument("-t", "--link_type")

    def handle(self, *args, **options):
        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()

        self.goitein = Creator.objects.get(last_name="Goitein")
        self.unpublished = SourceType.objects.get(type="Unpublished")
        self.jewish_traders = Source.objects.get(
            title="Letters of Medieval Jewish Traders"
        )

        self.stats = Counter()
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        self.footnote_contenttype = ContentType.objects.get_for_model(Footnote)
        self.source_contenttype = ContentType.objects.get_for_model(Source)
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        self.csv_path = options.get("csv")
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
        for key, value in sorted(self.stats.items()):
            self.stdout.write(f"\t{key}: {value}")

    # HELPERS -------------------------

    def get_document(self, pgpid):
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

    def log_change(self, obj, contenttype, message):
        # create log entry so there is a record of adding/updating urls
        LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=contenttype,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message=message,
            action_flag=CHANGE,
        )

    # TYPED TEXT -------------------

    def get_typed_text_source(self, doc):
        """Get Goiteins typed text volume given the shelfmark"""
        volume = Source.get_volume(doc.shelfmark)
        source = Source.objects.get_or_create(title_en="typed texts", volume=volume)
        source.url = "https://geniza.princeton.edu/indexcards/"
        source.source_type = self.unpublished
        source.authors.add(self.goitein)
        source.save()
        return source

    def parse_typed_text(self, doc, row):
        base_url = "https://commons.princeton.edu/media/geniza/"
        source = self.get_typed_text_source(doc)
        footnote = Footnote.get_or_create(source=source, content_object=doc)
        footnote.url = url
        footnote.doc_relation = [Footnote.EDITION]
        footnote.save()

    # INDEX CARDS -------------------

    def get_indexcard_source(self, doc):
        """Get or create the index card source related to a given document"""
        volume = Source.get_volume(doc.shelfmark)
        source = Source.objects.get_or_create(title="Index Cards", volume=volume)
        source.url = "https://geniza.princeton.edu/indexcards/"
        source.source_type = self.unpublished
        source.authors.add(goitein)
        return source

    def parse_indexcard(self, doc, row):
        url = f"https://geniza.princeton.edu/indexcards/index.php?a=card&id={row['link_target']}"
        source = self.get_indexcard_source(doc)
        footnote = Footnote.get_or_create(source=source, content_object=doc)
        footnote.url = url
        footnote.doc_relation = [Footnote.DISCUSSION]
        footnote.save()

    # JEWISH TRADERS -------------------

    def parse_jewish_traders(self, doc, row):
        url = f"https://s3.amazonaws.com/goitein-lmjt/{row['link_target']}"
        footnote = Footnote.get_or_create(
            source=self.jewish_traders, content_object=doc
        )
        footnote.url = url
        footnote.doc_relation = [Footnote.TRANSLATION]
        footnote.save()

    # INDIA TRADERS -------------------

    def get_india_book(self, row):
        book_part = (
            row["link_title"]
            .split("India Traders of the Middle Ages, ")[1]
            .split("-")[0]
        )
        rn_mapper = {"I": 1, "II": 2, "III": 3}
        return Source.objects.get(title=f"India Book {rn_mapper[book_part]}")

    def parse_india_traders(self, doc, row):
        url = f"https://s3.amazonaws.com/goitein-india-traders/{row['link_target']}"
        source = self.get_india_book(row)
        footnote = Footnote.get_or_create(source=source, content_object=doc)
        footnote.doc_relation = [Footnote.TRANSLATION]

    # PROCESS ENTRY --------------------

    # TODO: Start tests here (lookup parametrize test)
    def add_link(self, row):
        if (self.link_type and self.link_type != row["link_type"]) or (
            row["link_type"] in self.skipped_types
        ):
            return

        doc = self.get_document(row["object_id"])
        if not doc:
            return

        # Get new or updated footnote and source for each link type
        if row["link_type"] == "goitein_note":
            self.parse_typed_text(doc, row)
        elif row["link_type"] == "indexcard":
            self.parse_indexcard(doc, row)
        elif row["link_type"] == "jewish-traders":
            self.parse_jewish_traders(doc, row)
        elif row["link_type"] == "india-traders":
            self.parse_india_traders(doc, row)
        else:
            self.stats["document_skipped"] += 1
