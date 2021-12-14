import csv
import re
from collections import Counter

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import MultipleObjectsReturned
from django.core.management.base import BaseCommand, CommandError
from django.db import models

# from parasolr.django.signals import IndexableSignalHandler
from rich.progress import Progress

from geniza.corpus.models import Document
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


class Command(BaseCommand):
    """Imports a CSV export of the Geniza v3 links database as footnotes
    associated with Goitein sources and Jewish and Indian trader sources.
    Expects a CSV file to include the following columns:
    object_id link_type link_target
    """

    help = __doc__

    # the commented out ones are expected, but we don't actually use them;
    # only report on the required
    required_headers = [
        # "linkID",
        "object_id",
        "link_type",
        # "link_title",
        "link_target",
        # "link_attribution",
    ]

    # these link types are not handled by this script
    ignore_link_types = ["image", "iiif", "transcription", "cudl"]

    v_normal = 1

    # stats used in summary output or other counts
    stats_fields = [
        "imported",
        "ignored",
        "errored",
        "document_not_found",
        "sources_created",
        "footnotes_created",
        "footnotes_updated",
        "total",
    ]

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)
        parser.add_argument(
            "-t", "--link_type", help="Only process the specified link type (optional)"
        )

    def setup(self, options):
        # load authors, sources, source types, etc that will be needed
        self.goitein = Creator.objects.get(last_name="Goitein")
        self.unpublished = SourceType.objects.get(type="Unpublished")
        self.jewish_traders = Source.objects.get(
            title="Letters of Medieval Jewish Traders"
        )
        # load all volumes of india book into a dict for easy lookup
        self.india_book = {
            source.title: source
            for source in Source.objects.filter(title__startswith="India Book")
        }

        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        self.footnote_contenttype = ContentType.objects.get_for_model(Footnote)
        self.source_contenttype = ContentType.objects.get_for_model(Source)
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

    def handle(self, *args, **options):
        # disconnect solr indexing signals
        # IndexableSignalHandler.disconnect()

        self.setup()
        self.link_type = options.get("link_type")
        self.verbosity = options.get("verbosity", self.v_normal)
        # initialize stats values, since they don't always all get set
        self.stats = {stat: 0 for stat in self.stats_fields}
        # rough total for progress bar based on current number of rows in links.csv
        # *with* link types we care about (end of the file is largely ignored)
        starting_total = 10000  # 16300 = closer to real total

        csv_path = options.get("csv")
        try:
            with open(csv_path) as f:
                csvreader = csv.DictReader(f)
                with Progress(expand=True) as progress:
                    task = progress.add_task("Importing...", total=starting_total)

                    for i, row in enumerate(csvreader):
                        # on the first row, check the headers
                        if i == 0:
                            if not all(
                                [header in row for header in self.required_headers]
                            ):
                                raise CommandError(
                                    f"CSV is missing required fields: {self.required_headers}"
                                )
                        imported = self.add_link(row)
                        if imported == -1:  # -1 indicates ignored on purpose
                            self.stats["ignored"] += 1
                        elif imported:  # true == success
                            self.stats["imported"] += 1
                        else:  # otherwise, we failed to import
                            self.stats["errored"] += 1

                        self.stats["total"] += 1
                        updated_total = max(starting_total, self.stats["total"])
                        progress.update(task, advance=1, total=updated_total)
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")

        # summarize what was done
        self.stdout.write(
            """Imported {imported:,} links; ignored {ignored:,}; failed to import {errored:,}.
{document_not_found:,} documents not found in database.
Created {sources_created:,} new sources.
Created {footnotes_created:,} new footnotes; updated {footnotes_updated:,}.
""".format(
                **self.stats
            )
        )

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
            if self.verbosity > self.v_normal:
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

    def create_footnote(self, doc, source, url, doc_relation):
        # TODO: revise logic to account for the fact that some document
        # are discussed on more than one goitein index card

        # look for an existing footnote to update with the new url;
        # get or create doesn't work because not all parameters match (i.e., url)
        source_notes = doc.footnotes.filter(source=source).all()
        # if a footnote with the requested url and document relation exists
        existing_link = source_notes.filter(
            url=url, doc_relation__contains=[doc_relation]
        )
        if existing_link.exists():
            return existing_link.first()

        # otherwise, use the first matching footnote with no url
        footnote = source_notes.exclude(url="").first()
        # NOTE: it might be possible for there to be multiple matches,
        # but that seems to be a data error that has been corrected
        # Warn if there is more than one match?

        created = False
        if not footnote:
            # if a footnote was not found for the requested source, create one
            footnote = Footnote.objects.create(source=source, content_object=doc)
            created = True
            self.stats["footnotes_created"] += 1

        footnote.url = url
        footnote.doc_relation = doc_relation
        # only save if changed
        if footnote.has_changed("url") or footnote.has_changed("doc_relation"):
            footnote.save()
            if not created:
                # only count as an update if not newly created
                self.stats["footnotes_updated"] += 1

        # return the footnote to indicate success
        return footnote

    def get_goitein_source(self, doc=None, title=None, url=None):
        # TODO: Add URL for index cards?
        volume = Source.get_volume_from_shelfmark(doc.shelfmark)
        # common source options used to find or create our new source
        source_opts = {
            "title_en": title,
            "volume": Source.get_volume_from_shelfmark(doc.shelfmark),
            "source_type": self.unpublished,
        }
        # set url if specified
        if url:
            source_opts["url"] = url
        # we can't filter by author on get_or_create, so check first
        source = Source.objects.filter(
            authors__last_name="Goitein", **source_opts
        ).first()

        # if the volume doesn't already exist, create it
        if not source:
            source = Source.objects.create(**source_opts)
            source.authors.add(self.goitein)
            source.save()
            self.stats["sources_created"] += 1

        return source

    def get_india_book(self, title):
        book_part = title.split("India Traders of the Middle Ages, ")[1].split("-")[0]
        # links database uses roman numerals but in PGP 4 they are numbers; convert for lookup
        rn_mapper = {"I": 1, "II": 2, "III": 3}
        # sources in the database use the shorthand title "India Book"
        return self.india_book[f"India Book {rn_mapper[book_part]}"]

    # PROCESS ENTRY --------------------

    def add_link(self, row):
        # if a single link type has been specified and this row doesn't match, bail out;
        # if this is an unsupported link type, bail out
        if (self.link_type and row["link_type"] != self.link_type) or row[
            "link_type"
        ] in self.ignore_link_types:
            return -1  # return -1 to differentiate ignored instead of skipped

        # if document is not found, bail out
        doc = self.get_document(row["object_id"])
        if not doc:
            return

        if row["link_type"] == "goitein_note":
            # ?: Because this function takes up so much space, it may be easier
            #  to simply just write out the 4-5 lines here. What do you think?
            return self.create_footnote(
                doc=doc,
                source=self.get_goitein_source(doc=doc, title="typed texts"),
                url=f"https://commons.princeton.edu/media/geniza/{row['link_target']}",
                doc_relation=[Footnote.EDITION],
            )
        if row["link_type"] == "indexcard":
            return self.create_footnote(
                doc=doc,
                source=self.get_goitein_source(
                    doc=doc,
                    title="index cards",
                    url="https://geniza.princeton.edu/indexcards/",
                ),
                url=f"https://geniza.princeton.edu/indexcards/index.php?a=card&id={row['link_target']}",
                doc_relation=[Footnote.DISCUSSION],
            )
        if row["link_type"] == "jewish-traders":
            return self.create_footnote(
                doc=doc,
                source=self.jewish_traders,
                url=f"https://s3.amazonaws.com/goitein-lmjt/{row['link_target']}",
                doc_relation=[Footnote.TRANSLATION],
            )
        if row["link_type"] == "india-traders":
            return self.create_footnote(
                doc=doc,
                source=self.get_india_book(row["link_title"]),
                url=f"https://s3.amazonaws.com/goitein-india-traders/{row['link_target']}",
                doc_relation=[Footnote.TRANSLATION],
            )
