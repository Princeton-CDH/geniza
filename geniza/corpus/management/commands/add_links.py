import csv
import re
from os.path import basename, dirname
from urllib.parse import quote

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

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
        "link_title",
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

    def setup(self):
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

        self.content_types = {
            Footnote: ContentType.objects.get_for_model(Footnote),
            Source: ContentType.objects.get_for_model(Source),
        }
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

    def handle(self, *args, **options):
        # disconnect solr indexing signals
        # IndexableSignalHandler.disconnect()

        self.setup()
        self.link_type = options.get("link_type")
        self.verbosity = options.get("verbosity", self.v_normal)
        # initialize stats values, since they don't always all get set
        self.stats = {stat: 0 for stat in self.stats_fields}
        # initialize report of not found documents
        self.not_found_documents = []
        original_headers = []
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
                            original_headers = list(row.keys())
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

        # generate CSV report of documents that could not be found
        if len(self.not_found_documents) > 0:
            self.generate_csv_report(csv_path=csv_path, csv_headers=original_headers)

    def log_action(self, obj, action=CHANGE):
        # create log entry so there is a record of adding/updating urls
        message = "%s by add_links script" % (
            "Created" if action == ADDITION else "Updated"
        )
        LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=self.content_types[obj.__class__].pk,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message=message,
            action_flag=action,
        )

    def set_footnote_url(self, doc, source, url, doc_relation, location=""):
        """Set the requested url on a footnote for the specified document,
        associated with the requested source. If an appropriate footnote
        exists without a url, it will be updated. If not, a new one will
        be created. If a footnote with the requested url and document
        relation already exists, no changes are made, unless a location
        needs to be set. Returns the matching footnote to indicate success."""

        # look for an existing footnote to update with the new url;
        # get or create doesn't work because not all parameters match (i.e., url)
        source_notes = doc.footnotes.filter(source=source).all()
        # check if a footnote with the requested url and document relation already exists
        for note in source_notes:
            # if url and document relation are already set, only update location (if blank)
            if note.url == url and doc_relation in note.doc_relation:
                if not note.location:
                    note.location = location
                    note.save()
                    self.stats["footnotes_updated"] += 1
                    self.log_action(note)
                return note

        # otherwise, use the first matching footnote with no url
        # Don't update any footnotes with existing urls to avoid losing information;
        # Note that some documents are discussed on more than one index card,
        # and we don't want to overwrite the url for the first with the second.
        notes_without_url = [note for note in source_notes if not note.url]
        if notes_without_url:
            # NOTE: could warn if there is more than one here...
            footnote = notes_without_url[0]
            # set the url
            footnote.url = url
            # ensure document relation is set accurately
            footnote.doc_relation = doc_relation
            # set the location
            footnote.location = location
            # save the change and update the count
            footnote.save()
            self.stats["footnotes_updated"] += 1
            self.log_action(footnote)

        # if an appropriate footnote was not found, create a new one
        else:
            footnote = Footnote.objects.create(
                source=source,
                content_object=doc,
                url=url,
                doc_relation=doc_relation,
                location=location,
            )
            self.stats["footnotes_created"] += 1
            self.log_action(footnote, action=ADDITION)

        # return the footnote to indicate success
        return footnote

    def get_goitein_source(self, doc, title):
        # common source options used to find or create our new source
        source_opts = {
            "title_en": title,
            "volume": Source.get_volume_from_shelfmark(doc.shelfmark),
            "source_type": self.unpublished,
        }
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
            self.log_action(source, action=ADDITION)

        return source

    def get_india_book(self, title):
        book_part = title.split("India Traders of the Middle Ages, ")[1].split("-")[0]
        # links database uses roman numerals but in PGP 4 they are numbers; convert for lookup
        rn_mapper = {"I": 1, "II": 2, "III": 3}
        # sources in the database use the shorthand title "India Book"
        return self.india_book[f"India Book {rn_mapper[book_part]}"]

    # base url target for each supported link type
    base_url = {
        "goitein_note": "https://commons.princeton.edu/media/geniza/",
        "indexcard": "https://geniza.princeton.edu/indexcards/"
        + quote("index.php?a=card&id="),
        "jewish-traders": "https://s3.amazonaws.com/goitein-lmjt/",
        "india-traders": "https://s3.amazonaws.com/goitein-india-traders/",
    }

    # document relation is known based on type;
    # goitein typed texts provide transcriptions, index cards have discussion,
    # and both jewish and india traders provide translations
    document_relation = {
        "goitein_note": Footnote.EDITION,
        "indexcard": Footnote.DISCUSSION,
        "jewish-traders": Footnote.TRANSLATION,
        "india-traders": Footnote.TRANSLATION,
    }

    def add_link(self, row):
        # if a single link type has been specified and this row doesn't match, bail out;
        # if this is an unsupported link type, bail out
        link_type = row["link_type"]

        if (self.link_type and link_type != self.link_type) or row[
            "link_type"
        ] in self.ignore_link_types:
            return -1  # return -1 to differentiate ignored instead of skipped

        # get document by id; if not found, bail out
        doc = Document.get_by_any_pgpid(int(row["object_id"]))
        if not doc:
            self.stats["document_not_found"] += 1
            self.not_found_documents += [row]
            if self.verbosity > self.v_normal:
                self.stdout.write(
                    "Document %s not found in database" % row["object_id"]
                )
            return

        # target url: combine base url for this link type with link target from csv
        target_url = "".join([self.base_url[link_type], quote(row["link_target"])])
        # get doc relation for this link type
        doc_relation = self.document_relation[link_type]

        # get source and location based on the link type
        if link_type == "goitein_note":
            source = self.get_goitein_source(doc=doc, title="typed texts")
            base_name = basename(row["link_target"])
            try:  # use base name up to PGPID for goitein texts
                end_index = base_name.index("(PGPID")
            except ValueError:  # if PGPID not present, use base name up to extension
                end_index = base_name.rindex(".") if "." in base_name else 0
            # use string up to end_index and strip whitespace for location
            location = base_name[:end_index].strip() if end_index else base_name.strip()
        elif link_type == "indexcard":
            source = self.get_goitein_source(
                doc=doc,
                title="index cards",
            )
            # use card #target for location
            location = "card #%s" % row["link_target"]
        elif link_type == "jewish-traders":
            source = self.jewish_traders
            # use document number without extension (e.g. "01.pdf" becomes "01") for location
            base_name = row["link_target"]
            no_ext = (
                base_name[: base_name.rindex(".")] if "." in base_name else base_name
            )
            m = re.search(r"(\d+)", no_ext)
            location = ("document #%s" % m.groups(0)) if m else no_ext
        elif link_type == "india-traders":
            source = self.get_india_book(row["link_title"])
            # use filename without extension (e.g. "I-27-28.pdf" becomes "I-27-28") for location
            base_name = row["link_target"]
            no_ext = (
                base_name[: base_name.rindex(".")] if "." in base_name else base_name
            )
            location = no_ext.strip()

        # create or update footnote with the target url, beasd on all the other parameters determined
        return self.set_footnote_url(
            doc=doc,
            source=source,
            url=target_url,
            doc_relation=doc_relation,
            location=location,
        )

    def generate_csv_report(self, csv_path, csv_headers):
        """Generate a CSV containing the rows of the original CSV for which a document
        could not be found."""

        # basename without extension
        original_csv = (
            basename(csv_path)[: basename(csv_path).rindex(".")]
            if "." in csv_path
            else basename(csv_path)
        )
        # save in same directory as original CSV
        nf_report_path = dirname(csv_path) + (
            "/documents_not_found_in_%s.csv" % original_csv
        )
        # reconstruct CSV header and write rows
        with open(nf_report_path, "w+") as f:
            csv_writer = csv.DictWriter(f, fieldnames=csv_headers)
            csv_writer.writeheader()
            # append each row saved in not_found_documents
            for not_found_row in self.not_found_documents:
                csv_writer.writerow(not_found_row)

        self.stdout.write("Saved report of documents not found to %s." % nf_report_path)
