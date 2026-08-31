import csv
from collections import Counter

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from parasolr.django.signals import IndexableSignalHandler

from geniza.corpus.models import Document
from geniza.footnotes.models import (
    Authorship,
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)


class SkipRow(Exception):
    """Raised to skip a CSV row for a stated reason without aborting the run."""


class Command(BaseCommand):
    """One-off ingest of Posen Library translations from a CSV. Creates a new
    "Book Section" Source per row, and either:

    * Column H == "no": also creates a new "Translation" (content-less)
      `Footnote` linking the source to the document matched by the row's PGPID;
      existing footnotes are left untouched.
    * Column H == "yes": reassigns the existing "Digital Translation" footnote
      (id in Column I) from its current source to the new source.

    Skips and reports any data issues."""

    help = __doc__

    # zero-indexed CSV columns, matching spreadsheet columns A-M
    COL_PGPID = 1  # pgpid
    COL_PGP_URL = 4  # url
    COL_TITLE = 6  # Source title / chapter name
    COL_REASSIGN = 7  # "no" => new source + footnote; "yes" => reassign
    COL_FOOTNOTE_ID = 8  # existing footnote to reassign, for "yes" rows
    COL_CREATOR_IDS = 10  # Creator pks, separated by ";" or ","
    COL_POSEN_URL = 11  # stable Posen URL -> Source.url

    # constant Source field values shared by every created Posen source
    SOURCE_YEAR = 2026
    SOURCE_PUBLISHER = "Yale University Press"
    SOURCE_PLACE = "New Haven, Connecticut and London"
    SOURCE_JOURNAL = "Posen Library of Jewish Culture and Civilization"
    SOURCE_VOLUME = "3"
    SOURCE_TYPE = "Book Section"
    SOURCE_LANGUAGE = "English"

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str, help="Path to the input CSV file")
        parser.add_argument(
            "-d",
            "--dryrun",
            action="store_true",
            help="Process the CSV and report actions, but roll back all changes",
        )
        parser.add_argument(
            "--skip-indexing",
            action="store_true",
            default=False,
            help="Turn off Solr indexing as changes are made (on by default)",
        )

    def handle(self, *args, **options):
        self.dryrun = options["dryrun"]
        self.stats = Counter()
        # (row number, pgpid, reason) tuples for reporting
        self.skipped = []

        if options["skip_indexing"]:
            IndexableSignalHandler.disconnect()

        # look up shared/related records once; fail if setup is missing
        try:
            self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        except User.DoesNotExist:
            raise CommandError(
                "Script user '%s' not found; cannot record log entries"
                % settings.SCRIPT_USERNAME
            )
        try:
            self.book_section = SourceType.objects.get(type=self.SOURCE_TYPE)
        except SourceType.DoesNotExist:
            raise CommandError("SourceType '%s' not found" % self.SOURCE_TYPE)
        try:
            self.english = SourceLanguage.objects.get(name=self.SOURCE_LANGUAGE)
        except SourceLanguage.DoesNotExist:
            raise CommandError("SourceLanguage '%s' not found" % self.SOURCE_LANGUAGE)

        self.document_contenttype = ContentType.objects.get_for_model(Document)
        self.source_contenttype = ContentType.objects.get_for_model(Source)
        self.footnote_contenttype = ContentType.objects.get_for_model(Footnote)

        try:
            with open(options["csv"]) as f:
                # index by column position rather than header name;
                # headers are long and contain commas/newlines
                reader = csv.reader(f)
                # discard header row
                next(reader, None)
                with transaction.atomic():
                    for i, row in enumerate(reader, start=2):
                        self.process_row(i, row)
                    if self.dryrun:
                        transaction.set_rollback(True)
        except FileNotFoundError:
            raise CommandError("CSV file not found: %s" % options["csv"])

        self.report()

    def process_row(self, row_num, row):
        """Process a single CSV row, skipping (and recording) any row that
        cannot be processed cleanly"""
        # ignore empty row
        if not any(cell.strip() for cell in row):
            return

        pgpid_raw = self.cell(row, self.COL_PGPID)
        try:
            # use one atomic transaction per row to allow rollback
            with transaction.atomic():
                reassign = self.cell(row, self.COL_REASSIGN).strip().lower()
                creator_ids = self.parse_creator_ids(row)

                if reassign == "no":
                    self.create_source_and_footnote(row, creator_ids)
                elif reassign == "yes":
                    self.create_source_and_reassign(row, creator_ids)
                else:
                    raise SkipRow(
                        "unrecognized Column H value %r (expected 'yes' or 'no')"
                        % self.cell(row, self.COL_REASSIGN).strip()
                    )
        except SkipRow as err:
            self.stats["skipped"] += 1
            self.skipped.append((row_num, pgpid_raw, str(err)))
            self.stdout.write(
                self.style.WARNING(
                    "Row %d (PGPID %r) skipped: %s" % (row_num, pgpid_raw, err)
                )
            )

    def create_source_and_footnote(self, row, creator_ids):
        """Handle a Column H == "no" row: create the Posen source and a new
        content-less Translation footnote on the row's single document."""
        document = self.get_document(row)
        source, created = self.get_or_create_source(row, creator_ids)

        # idempotent: don't create a second footnote linking this source + document
        if Footnote.objects.filter(
            source=source,
            content_type=self.document_contenttype,
            object_id=document.pk,
        ).exists():
            return

        footnote = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=[Footnote.TRANSLATION],
        )
        self.stats["footnotes_created"] += 1
        self.log(
            self.footnote_contenttype,
            footnote,
            ADDITION,
            "Created Translation footnote for Posen Library source",
        )

    def create_source_and_reassign(self, row, creator_ids):
        """Handle a Column H == "yes" row: create the Posen source and reassign
        the existing digital-translation footnote (Column I) to it."""
        footnote = self.get_footnote(row)
        source, created = self.get_or_create_source(row, creator_ids)

        if footnote.source_id == source.pk:
            return  # already reassigned (e.g. re-run)

        if Footnote.DIGITAL_TRANSLATION not in (footnote.doc_relation or []):
            # proceed as instructed, but flag the unexpected relation type
            self.stdout.write(
                self.style.WARNING(
                    "Footnote %d is not a Digital Translation; reassigning anyway"
                    % footnote.pk
                )
            )

        old_source = footnote.source
        footnote.source = source
        footnote.save()
        self.stats["footnotes_reassigned"] += 1
        self.log(
            self.footnote_contenttype,
            footnote,
            CHANGE,
            "Reassigned footnote from source %r to new Posen Library source"
            % str(old_source),
        )

    def get_or_create_source(self, row, creator_ids):
        """Return the Posen source for this row, creating it (with authorship,
        language, and slug) if an equivalent one does not already exist.
        Matching on title + authors keeps the command safe to re-run."""
        title = self.cell(row, self.COL_TITLE).strip()
        if not title:
            raise SkipRow("missing title (Column G)")

        # reuse an existing identical source if present;
        # prefetch authorships for efficiency
        for candidate in Source.objects.filter(
            title=title,
            journal=self.SOURCE_JOURNAL,
            volume=self.SOURCE_VOLUME,
            year=self.SOURCE_YEAR,
            source_type=self.book_section,
        ).prefetch_related("authorship_set"):
            existing_ids = [
                a.creator_id
                for a in candidate.authorship_set.all().order_by("sort_order")
            ]
            if existing_ids == creator_ids:
                return candidate, False

        source = Source.objects.create(
            title=title,
            year=self.SOURCE_YEAR,
            publisher=self.SOURCE_PUBLISHER,
            place_published=self.SOURCE_PLACE,
            journal=self.SOURCE_JOURNAL,
            volume=self.SOURCE_VOLUME,
            url=self.cell(row, self.COL_POSEN_URL).strip(),
            source_type=self.book_section,
        )
        source.languages.add(self.english)
        for order, creator_id in enumerate(creator_ids, start=1):
            Authorship.objects.create(
                source=source, creator_id=creator_id, sort_order=order
            )
        # slug generation depends on the related creators, so run it last
        source.generate_slug()
        source.save()

        self.stats["sources_created"] += 1
        self.log(
            self.source_contenttype,
            source,
            ADDITION,
            "Created Posen Library book section source",
        )
        return source, True

    def parse_creator_ids(self, row):
        """Parse Column K into an ordered list of existing Creator pks."""
        raw = self.cell(row, self.COL_CREATOR_IDS)
        creator_ids = []
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit():
                raise SkipRow("non-numeric Creator ID %r (Column K)" % part)
            creator_ids.append(int(part))

        if not creator_ids:
            raise SkipRow("missing Creator ID(s) (Column K)")

        found = set(
            Creator.objects.filter(pk__in=creator_ids).values_list("pk", flat=True)
        )
        missing = [cid for cid in creator_ids if cid not in found]
        if missing:
            raise SkipRow(
                "Creator ID(s) not found: %s" % ", ".join(str(cid) for cid in missing)
            )
        return creator_ids

    def get_document(self, row):
        """Resolve PGPID in Column B to a Document, skipping rows
        with multiple/blank/non-numeric ids."""
        raw = self.cell(row, self.COL_PGPID).strip()
        if not raw.isdigit():
            raise SkipRow(
                "Column B is not a single numeric PGPID (%r); handle manually" % raw
            )
        try:
            return Document.objects.get(pk=int(raw))
        except Document.DoesNotExist:
            raise SkipRow("no Document found for PGPID %s" % raw)

    def get_footnote(self, row):
        """Resolve the existing footnote id in Column I for a "yes" row."""
        raw = self.cell(row, self.COL_FOOTNOTE_ID).strip()
        if not raw.isdigit():
            raise SkipRow("missing/invalid footnote id %r (Column I)" % raw)
        try:
            return Footnote.objects.get(pk=int(raw))
        except Footnote.DoesNotExist:
            raise SkipRow("no Footnote found for id %s (Column I)" % raw)

    @staticmethod
    def cell(row, index):
        """Safely read a column, tolerating short rows"""
        return row[index] if index < len(row) else ""

    def log(self, content_type, obj, action_flag, message):
        """Record an admin log entry"""
        LogEntry.objects.log_action(
            user_id=self.script_user.pk,
            content_type_id=content_type.pk,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message=message,
            action_flag=action_flag,
        )

    def report(self):
        """Summarize created/reassigned records and list skipped rows."""
        if self.dryrun:
            self.stdout.write(self.style.NOTICE("DRY RUN — no changes committed"))
        self.stdout.write("Sources created: %d" % self.stats["sources_created"])
        self.stdout.write("Footnotes created: %d" % self.stats["footnotes_created"])
        self.stdout.write(
            "Footnotes reassigned: %d" % self.stats["footnotes_reassigned"]
        )
        self.stdout.write("Rows skipped: %d" % self.stats["skipped"])
        if self.skipped:
            self.stdout.write("\nSkipped rows (need manual handling):")
            for row_num, pgpid, reason in self.skipped:
                self.stdout.write("  row %d (PGPID %r): %s" % (row_num, pgpid, reason))
