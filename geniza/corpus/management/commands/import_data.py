import codecs
import csv
import json
import logging
import os
import re
from collections import defaultdict, namedtuple
from datetime import datetime
from operator import itemgetter
from string import punctuation

import requests
from dateutil.parser import ParserError, parse
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models
from django.utils.text import slugify
from django.utils.timezone import get_current_timezone, make_aware
from parasolr.django.signals import IndexableSignalHandler

from geniza.corpus.models import (
    Collection,
    Document,
    DocumentType,
    Fragment,
    LanguageScript,
    TextBlock,
)
from geniza.footnotes.models import (
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)

# mapping for csv header fields and local name we want to use
# if not specified, column will be lower-cased
csv_fields = {
    "libraries": {
        "Current List of Libraries": "current",
        "Library abbreviation": "lib_abbrev",
        "Collection abbreviation": "abbrev",
        "Location (current)": "location",
        "Collection (if different from library)": "collection",
    },
    "languages": {
        # lower case for each should be fine
    },
    "metadata": {
        "Shelfmark - Current": "shelfmark",
        "Input by (optional)": "input_by",
        "Date entered (optional)": "date_entered",
        "Recto or verso (optional)": "recto_verso",
        "Language (optional)": "language",
        "Text-block (optional)": "text_block",
        "Shelfmark - Historical (optional)": "shelfmark_historic",
        "Multifragment (optional)": "multifragment",
        "Link to image": "image_link",
        "Editor(s)": "editor",
        "Translator (optional)": "translator",
        "Notes2 (optional)": "notes",
        "Technical notes (optional)": "tech_notes",
    },
}

# events in document edit history with missing/malformed dates will replace
# missing portions with values from this date
DEFAULT_EVENT_DATE = datetime(2020, 1, 1)

# logging config: use levels as integers for verbosity option
logger = logging.getLogger("import")
logging.basicConfig()
LOG_LEVELS = {0: logging.ERROR, 1: logging.WARNING, 2: logging.INFO, 3: logging.DEBUG}


class Command(BaseCommand):
    "Import existing data from PGP spreadsheets into the database"

    logentry_message = "Imported via script"
    max_documents = None

    def add_arguments(self, parser):
        parser.add_argument("-m", "--max_documents", type=int)

    def setup(self, *args, **options):
        if not hasattr(settings, "DATA_IMPORT_URLS"):
            raise CommandError("Please configure DATA_IMPORT_URLS in local settings")

        # setup logging; default to WARNING level
        verbosity = options.get("verbosity", 1)
        logger.setLevel(LOG_LEVELS[verbosity])

        # load fixure containing known historic users (all non-active)
        call_command("loaddata", "historic_users", app_label="corpus", verbosity=0)
        logger.info("loaded 30 historic users")

        # ensure current active users are present, but don't try to create them
        # in a test environment because it's slow and requires VPN access
        active_users = ["rrichman", "mrustow", "ae5677", "alg4"]
        if "PYTEST_CURRENT_TEST" not in os.environ:
            present = User.objects.filter(username__in=active_users).values_list(
                "username", flat=True
            )
            for username in set(active_users) - set(present):
                call_command("createcasuser", username, staff=True, verbosity=verbosity)

        # Set dicts on the instance so they're not shared across instances
        self.doctype_lookup = {}
        self.content_types = {}
        self.collection_lookup = {}
        self.document_type = {}
        self.language_lookup = {}
        self.user_lookup = {}

        # fetch users created through migrations for easy access later; add one
        # known exception (accented character)
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.team_user = User.objects.get(username=settings.TEAM_USERNAME)
        self.user_lookup["Naim Vanthieghem"] = User.objects.get(username="nvanthieghem")

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()

        self.content_types = {
            model: ContentType.objects.get_for_model(model)
            for model in [Fragment, Collection, Document, LanguageScript, Source]
        }

        self.source_setup()

    def source_setup(self):
        # setup for importing editions & transcriptions

        # delete source records created on a previous run
        Creator.objects.all().delete()
        Source.objects.all().delete()
        Footnote.objects.all().delete()

        # load fixure with source creators referenced in the spreadsheet
        call_command("loaddata", "source_authors", app_label="footnotes", verbosity=0)
        # total TODO
        # logger.info("loaded ## source creators")

        # create source type lookup keyed on type
        self.source_types = {s.type: s for s in SourceType.objects.all()}
        # create source creator lookup keyed on last name
        self.source_creators = {c.last_name: c for c in Creator.objects.all()}

        # load transcription data as JSON. if no file is provided, warn but
        # don't error.
        try:
            with open(settings.TRANSCRIPTIONS_JSON_FILE) as json_file:
                self.transcriptions = json.load(json_file)
        except (AttributeError, FileNotFoundError):
            logger.warning("No transcriptions provided")
            self.transcriptions = {}

    def handle(self, *args, **options):
        self.setup(*args, **options)
        self.max_documents = options.get("max_documents")
        self.import_collections()
        self.import_languages()
        self.import_documents()

    def get_csv(self, name, schema=None):
        # given a name for a file in the configured data import urls,
        # load the data by url and initialize and return a generator
        # of namedtuple elements for each row
        csv_url = settings.DATA_IMPORT_URLS.get(name, None)
        if not csv_url:
            raise CommandError("Import URL for %s is not configured" % name)
        response = requests.get(csv_url, stream=True)
        if response.status_code != requests.codes.ok:
            raise CommandError("Error accessing CSV for %s: %s" % (name, response))

        csvreader = csv.reader(codecs.iterdecode(response.iter_lines(), "utf-8"))
        header = next(csvreader)
        # Create a namedtuple based on headers in the csv
        # and local mapping of csv names to access names
        CsvRow = namedtuple(
            "%sCSVRow" % name,
            (
                csv_fields[(schema or name)].get(
                    col, slugify(col).replace("-", "_") or "empty_%d" % i
                )
                for i, col in enumerate(header)
                # NOTE: allows one empty header; more will cause an error
            ),
        )

        # iterate over csv rows and yield a generator of the namedtuple
        for count, row in enumerate(csvreader, start=1):
            yield CsvRow(*row)
            # if max documents is configured, bail out for metadata
            if (
                self.max_documents
                and name == "metadata"
                and count >= self.max_documents
            ):
                break

    def import_collections(self):
        # clear out any existing collections
        Collection.objects.all().delete()
        # import list of libraries and abbreviations
        # convert to list so we can iterate twice
        library_data = list(self.get_csv("libraries"))

        # create a collection entry for every row in the sheet with both
        # required values
        collections = []
        # at the same time, populate a library lookup to map existing data
        for row in library_data:
            # must have at least library or collection
            if row.library or row.collection:
                new_collection = Collection.objects.create(
                    library=row.library,
                    lib_abbrev=row.lib_abbrev,
                    abbrev=row.abbrev,
                    location=row.location,
                    name=row.collection,
                )
                collections.append(new_collection)

                # add the new object to library lookup
                # special case: CUL has multiple collections which use the
                # same library code in the metadata spreadsheet;
                # include collection abbreviation in lookup
                lookup_code = row.current
                if row.current == "CUL":
                    lookup_code = "%s_%s" % (row.current, row.abbrev)
                self.collection_lookup[lookup_code] = new_collection

        # create log entries to document when & how records were created
        self.log_creation(*collections)
        logger.info("Imported %d collections" % len(collections))

    def import_languages(self):
        LanguageScript.objects.all().delete()
        language_data = self.get_csv("languages")
        languages = []
        for row in language_data:
            # skip empty rows
            if not row.language and not row.script:
                continue

            lang = LanguageScript.objects.create(
                language=row.language,
                script=row.script,
                display_name=row.display_name or None,
            )

            # populate lookup for associating documents & languages;
            # use lower case spreadsheet name if set, or display name
            if row.display_name or row.spreadsheet_name:
                self.language_lookup[
                    (row.spreadsheet_name or row.display_name).lower()
                ] = lang
            languages.append(lang)

        # create log entries
        self.log_creation(*languages)
        logger.info("Imported %d languages" % len(languages))

    def add_document_language(self, doc, row):
        """Parse languages and set probable_language and language_notes"""
        notes_list = []
        if not row.language:
            return

        for lang in row.language.split(";"):
            lang = lang.strip()
            # Place language in the language note if there're any non-question
            # mark notes in language entry
            if re.search(r"\([^?]+\)", lang):
                notes_list.append(lang)
            is_probable = "?" in lang
            # remove parentheticals, question marks, "some"
            lang = re.sub(r"\(.+\)", "", lang).replace("some", "").strip("? ")

            lang_model = self.language_lookup.get(lang.lower())
            if not lang_model:
                logger.error(
                    f"language not found. PGPID: {row.pgpid}, Language: {lang}"
                )
            else:
                if is_probable:
                    doc.probable_languages.add(lang_model)
                else:
                    doc.languages.add(lang_model)

        if notes_list:
            doc.language_note = "\n".join(notes_list)
            doc.save()

    def get_old_pgpids(self, notes):
        if "PGPID" in notes:
            old_pgpids = notes.split(": ")[-1]
            return [int(old_pgpid) for old_pgpid in old_pgpids.split(", ")]
        return None
        # ?? Should this be []

    def get_notes(self, notes, tech_notes):
        IGNORE = [
            "India",
            "India; unsure of date entered by Geniza Lab team (historical, before 2015)",
            "India: addendum to IB IV",
            "Rustow, Lost Archive",
            "DISAGGREGATE",
        ]

        notes_to_set = []
        if notes not in IGNORE and "PGPID" not in notes:
            notes_to_set.append(notes)

        ## TECHNICAL NOTES
        # Unique values:
        """
            FGP stub
            scanned in drive
            ?scanned in drive
            Transcription needs to be uploaded*
            Transcription needs to be uploaded
            scanned in drive (TRANSCRIPTION)
            scanned in drive (TRANSLATION)
            not in Gil
            Scanned in drive
            scanned in drive 
            scanned in drive (TRANSCRIPTION + TRANSLATION)
            scanned in drive (TRANSCRIPTION & TRANSLATION)
        """

        if tech_notes == "not in Gil":
            GIL_NOTE = "Not published by Gil, pace FGP."
            notes_to_set.append(GIL_NOTE)

        if "scanned in drive" == tech_notes.strip("?"):
            SCANNED_GOITEIN_NOTE = "Look for Goitein scan in this folder: https://drive.google.com/drive/folders/1ZAWSK3ILoRyll0FafU61V5zdccx0CgaP?usp=sharing"
            notes_to_set.append(SCANNED_GOITEIN_NOTE)
        elif "scanned in drive" in tech_notes:
            detail = " and ".join(
                [t for t in ["transcription", "translation"] if t in tech_notes.lower()]
            )
            DETAIL_GOTEIN_SCAN_NOTE = (
                f"There is a {detail} in Goitein's notes that should be digitized."
            )
            notes_to_set.append(DETAIL_GOTEIN_SCAN_NOTE)

        return "\n".join(notes_to_set)

    def import_document(self, row):
        """Import a single document given a row from a PGP spreadsheet"""
        # skip any row with multiple types or flagged for demerge
        if ";" in row.type or "DISAGGREGATE" in row.notes:
            logger.warning("skipping PGPID %s (demerge)" % row.pgpid)
            self.docstats["skipped"] += 1
            return

        # create a reverse lookup for recto/verso labels used in the
        # spreadsheet to the codes used in the database
        recto_verso_lookup = {
            label.lower(): code for code, label in TextBlock.RECTO_VERSO_CHOICES
        }

        doctype = self.get_doctype(row.type)
        fragment = self.get_fragment(row)
        doc = Document.objects.create(
            id=row.pgpid or None,
            doctype=doctype,
            description=row.description,
            old_pgpids=self.get_old_pgpids(row.notes),
            notes=self.get_notes(row.notes, row.tech_notes),
        )
        doc.tags.add(*[tag.strip() for tag in row.tags.split("#") if tag.strip()])
        # associate fragment via text block
        TextBlock.objects.create(
            document=doc,
            fragment=fragment,
            # convert recto/verso value to code
            side=recto_verso_lookup.get(row.recto_verso, ""),
            region=row.text_block,
            subfragment=row.multifragment,
        )
        self.add_document_language(doc, row)
        self.docstats["documents"] += 1
        # create log entries as we go
        self.log_edit_history(
            doc, self.get_edit_history(row.input_by, row.date_entered, row.pgpid)
        )
        # parse editor & translator information to create sources
        # and associate with footnotes
        editor = row.editor.strip(".")
        if editor and editor not in self.editor_ignore:
            self.parse_editor(doc, editor)
        # treat translator like editor, but set translation flag
        if row.translator:
            self.parse_editor(doc, row.translator, translation=True)

        # keep track of any joins to handle on a second pass
        if row.joins.strip():
            self.joins.add((doc, row.joins.strip()))

    def import_documents(self):
        """Import all document given the PGP spreadsheets"""

        metadata = self.get_csv("metadata")
        demerged_metadata = self.get_csv("demerged", schema="metadata")

        Document.objects.all().delete()
        Fragment.objects.all().delete()
        LogEntry.objects.filter(
            content_type_id=self.content_types[Document].id
        ).delete()

        self.joins = set()
        self.docstats = defaultdict(int)

        for row in metadata:
            self.import_document(row)
        document_count_metadata = self.docstats["documents"]

        # update id sequence based on highest imported pgpid
        self.update_document_id_sequence()

        for row in demerged_metadata:
            # overwrite document if it already exists
            if row.pgpid and Document.objects.filter(id=row.pgpid).exists():
                logger.warning(f"Overwriting PGPID {row.pgpid} with demerge")
                Document.objects.filter(id=row.pgpid).delete()
                self.docstats["overwritten"] += 1
            self.import_document(row)

        # handle joins collected on the first pass
        for doc, join in self.joins:
            initial_shelfmark = doc.shelfmark
            for shelfmark in join.split(" + "):
                # skip the initial shelfmark, already associated
                if shelfmark == initial_shelfmark:
                    continue
                # get the fragment if it already exists
                join_fragment = Fragment.objects.filter(shelfmark=shelfmark).first()
                # if not, create a stub fragment record
                if not join_fragment:
                    join_fragment = Fragment.objects.create(shelfmark=shelfmark)
                    self.log_creation(join_fragment)
                # associate the fragment with the document
                doc.fragments.add(join_fragment)
        document_count_demerged = self.docstats["documents"] - document_count_metadata

        logger.info(
            f"Imported {document_count_metadata} documents from the metadata spreadsheet and skipped {self.docstats['skipped']}. "
            f"Imported {document_count_demerged} documents from the demerged spreadsheet. "
            f"Overwrote {self.docstats['overwritten']} documents. "
            f"Parsed {len(self.joins)} joins. "
        )

    def get_doctype(self, dtype):
        # don't create an empty doctype
        dtype = dtype.strip()
        if not dtype or dtype == "Unknown":
            return

        doctype = self.doctype_lookup.get(dtype)
        # if not yet in our local lookup, get from the db
        if not doctype:
            doctype = DocumentType.objects.get_or_create(name=dtype)[0]
            self.doctype_lookup[dtype] = doctype

        return doctype

    def get_collection(self, data):
        lib_code = data.library.strip()
        # differentiate CUL collections based on shelfmark
        if lib_code == "CUL":
            for cul_collection in ["T-S", "CUL Or.", "CUL Add."]:
                if data.shelfmark.startswith(cul_collection):
                    lib_code = "CUL_%s" % cul_collection.replace("CUL ", "")
                    break
            # if code is still CUL, there is a problem
            if lib_code == "CUL":
                logger.warning(
                    "CUL collection not determined for %s (PGPID %s)"
                    % (data.shelfmark, data.pgpid)
                )
        return self.collection_lookup.get(lib_code)

    def get_fragment(self, data):
        # get the fragment for this document if it already exists;
        # if it doesn't, create it
        fragment = Fragment.objects.filter(shelfmark=data.shelfmark).first()
        if fragment:
            return fragment

        # if fragment was not found, create it
        fragment = Fragment.objects.create(
            shelfmark=data.shelfmark,
            # todo: handle missing libraries (set from shelfmark?)
            collection=self.get_collection(data),
            old_shelfmarks=data.shelfmark_historic,
            is_multifragment=bool(data.multifragment),
            url=data.image_link,
            iiif_url=self.get_iiif_url(data),
        )
        # log object creation
        self.log_creation(fragment)
        return fragment

    def get_iiif_url(self, data):
        """Get IIIF Manifest URL for a fragment when possible"""

        # cambridge iiif manifest links use the same id as view links
        # NOTE: should exclude search link like this one:
        # https://cudl.lib.cam.ac.uk/search?fileID=&keyword=T-s%2013J33.12&page=1&x=0&y=
        extlink = data.image_link
        if "cudl.lib.cam.ac.uk/view/" in extlink:
            iiif_link = extlink.replace("/view/", "/iiif/")
            # view links end with /1 or /2 but iiif link does not include it
            iiif_link = re.sub(r"/\d$", "", iiif_link)
            return iiif_link

        # TODO: get new figgy iiif urls for JTS images based on shelfmark
        # if no url, return empty string for blank instead of null
        return ""

    def log_creation(self, *objects):
        # create log entries to document when & how records were created
        # get content type based on first object
        content_type = self.content_types[objects[0].__class__]
        for obj in objects:
            LogEntry.objects.log_action(
                user_id=self.script_user.id,
                content_type_id=content_type.pk,
                object_id=obj.pk,
                object_repr=str(obj),
                change_message=self.logentry_message,
                action_flag=ADDITION,
            )

    def get_user(self, name, pgpid=None):
        """Find a user account based on a provided name, using a simple cache.

        If not found, tries to use first/last initials for lookup. If all else
        fails, use the generic team account (TEAM_USERNAME).
        """

        # check the cache first
        user = self.user_lookup.get(name)
        if user:
            logger.debug(f"using cached user {user} for {name} on PGPID {pgpid}")
            return user

        # person with given name(s) and last name – case-insensitive lookup
        if " " in name:
            given_names, last_name = [
                sname.strip(punctuation) for sname in name.rsplit(" ", 1)
            ]
            try:
                user = User.objects.get(
                    first_name__iexact=given_names, last_name__iexact=last_name
                )
            except User.DoesNotExist:
                pass

        # initials; use first & last to do lookup
        elif name:
            name = name.strip(punctuation)
            first_i, last_i = name[0], name[-1]
            try:
                user = User.objects.get(
                    first_name__startswith=first_i, last_name__startswith=last_i
                )
            except User.DoesNotExist:
                pass

        # if we didn't get anyone through either method, warn and use team user
        if not user:
            logger.warning(
                f"couldn't find user {name} on PGPID {pgpid}; using {self.team_user}"
            )
            return self.team_user

        # otherwise add to the cache using requested name and return the user
        logger.debug(f"found user {user} for {name} on PGPID {pgpid}")
        self.user_lookup[name] = user
        return user

    def get_edit_history(self, input_by, date_entered, pgpid=None):
        """Parse spreadsheet "input by" and "date entered" columns to
        reconstruct the edit history of a single document.

        Output is a list of dict to pass to log_edit_history. Each event has
        a type (django log entry action flag), associated user, and date.

        This method is designed to output a list of events that matches the
        logic of the spreadsheet and is easy to reason about (chronologically
        ordered).
        """

        # split both fields by semicolon delimiter & remove whitespace
        all_input = [i.strip() for i in input_by.split(";") if i]
        all_dates = [d.strip() for d in date_entered.split(";") if d]

        # try to map every "input by" listing to a user account. for coauthored
        # events, add both users to a list – otherwise it's a one-element list
        # with the single user
        users = []
        for input_by in all_input:
            users.append([self.get_user(u, pgpid) for u in input_by.split(" and ")])

        # convert every "date entered" listing to a date object. if any parts of
        # the date are missing, fill with default values below. for details:
        # https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.parse
        dates = []
        for date in all_dates:
            try:
                dates.append(parse(date, default=DEFAULT_EVENT_DATE).date())
            except ParserError:
                logger.warning(f"failed to parse date {date} on PGPID {pgpid}")

        # make sure we have same number of users/dates by padding with None;
        # later we can assign missing users to the generic team user
        while len(users) < len(dates):
            users.insert(0, None)

        # moving backwards in time, pair dates with users and event types.
        # when there is a mismatch between number of users and dates, we want
        # to associate the more recent dates with users, since in general
        # we have more information the closer to the present we are. if we run
        # out of users to assign, we use the generic team user.
        events = []
        users.reverse()
        all_dates.reverse()
        for i, date in enumerate(reversed(dates)):

            # earliest date is creation; all others are revisions
            event_type = CHANGE if i < len(dates) - 1 else ADDITION

            # if we have a date without a user, assign to the whole team
            user = users[i] or (self.team_user,)

            # create events with this date and type for all the matching users.
            # if there was more than one user (coauthor), use the same type and
            # date to represent the coauthorship
            for u in user:
                events.append(
                    {
                        "type": event_type,
                        "user": u,
                        "date": date,
                        "orig_date": all_dates[i],
                    }
                )
            if len(user) > 1:
                logger.debug(f"found coauthored event for PGPID {pgpid}: {events[-2:]}")
            else:
                logger.debug(f"found event for PGPID {pgpid}: {events[-1]}")

        # sort chronologically and return
        events.sort(key=itemgetter("date"))
        return events

    sheet_add_msg = "Initial data entry (spreadsheet)"
    sheet_chg_msg = "Major revision (spreadsheet)"

    def log_edit_history(self, doc, events):
        """Given a Document and a sequence of events from get_edit_history,
        create corresponding Django log entries to represent that history.

        Always creates an entry by the script user (`SCRIPT_USERNAME`) with a
        timestamp of now to mark the import event itself.

        Optional `events` is list of dict from get_edit_history. Each event has
        a type (creation or revision), associated user, and timestamp.
        """

        # for each historic event, create a corresponding django log entry.
        # we use objects.create() instead of the log_action helper so that we
        # can control the timestamp.
        for event in events:
            dt = datetime(
                year=event["date"].year,
                month=event["date"].month,
                day=event["date"].day,
            )
            msg = (
                self.sheet_add_msg if event["type"] == ADDITION else self.sheet_chg_msg
            )
            LogEntry.objects.create(
                user=event["user"],  # FK in django
                content_type=self.content_types[Document],  # FK in django
                object_id=str(doc.pk),  # TextField in django
                object_repr=str(doc)[:200],  # CharField with limit in django
                change_message=f"{msg}, dated {event['orig_date']}",
                action_flag=event["type"],
                action_time=make_aware(dt, timezone=get_current_timezone()),
            )

        # log the actual import event as an ADDITION, since it marks the point
        # at which the object entered this database.
        LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=self.content_types[Document].pk,
            object_id=doc.pk,
            object_repr=str(doc),
            change_message=self.logentry_message,
            action_flag=ADDITION,
        )

    def update_document_id_sequence(self):
        # set postgres document id sequence to maximum imported pgpid
        cursor = connection.cursor()
        cursor.execute(
            "SELECT setval('corpus_document_id_seq', max(id)) FROM corpus_document;"
        )

    re_url = re.compile(r"(?P<url>https://[^ ]+)")

    # ignore these entries in the editor field:
    editor_ignore = [
        "awaiting transcription",
        "transcription listed on fgp",
        "transcription listed on fgp, awaiting digitization on pgp",
        "transcription listed in fgp, awaiting digitization on pgp",
        "source of transcription not noted in original pgp database",
        "source of transcription not noted in original pgp. complete transcription awaiting digitization",
        "yes",
        "partial transcription listed in fgp, awaiting digitization on pgp",
        "transcription (recto only) listed in fgp, awaiting digitization on pgp",
        "transcription in progress",
        "awaiting transcription (htr)",
        "transcription (verso only) listed in fgp, awaiting digitization on pgp",
    ]

    # re_docrelation = re.compile(r'^(. Also )?Ed. (and transl?.)? ?',
    re_docrelation = re.compile(
        r"^((also )?ed. ?(and trans(\.|l\.|lated) ?)?(by )?|(also )?trans.)", flags=re.I
    )

    # notes that may occur with an edition
    # - full transcription listed/awaiting ...
    # - with (minor) ..
    # - with corrections
    # - multiword parenthetical at the end of the edition
    re_ed_notes = re.compile(
        r'[.;,]["\'’”]? (?P<note>('
        + r"(full )?transcription (listed|awaiting|available|only).*$|"
        + r"(retyped )?(with )?minor|with corrections|with emendations).*$|"
        + r"compared with.*$|incorporat.*$|"
        + r"partial.*$|remainder.*$|(revised|rev\.) .*$|"
        + r"(translation )?await.*$|additions .*$"
        + r"(as )?corrected.*$|"
        + r"edited (here )?in comparison with.*$|"
        + r"[(]?see .*$|"
        + r"(\([\w\d]+ [\w\d.,-– \"']+\) ?$))",
        flags=re.I | re.U,
    )

    # regexes to pull out page or document location
    re_page_location = re.compile(
        r"[,.:] (?P<pages>((pp?|pgs)\. ?\d+([-–]\d+)?)|(\d+[-–]\d+)[a-z]?)"
        + r"( \[\d+\])?\.?",  # pp. 215-236 [219]
        flags=re.I,
    )
    # Doc, Doc., Document, # with numbers and or alpha-number
    re_doc_location = re.compile(
        r"(, )?\(?(?P<doc>(Doc(ument|\.)? ?#?|#|no\.) ?([A-Z]-)?\d+)\)?\.?", flags=re.I
    )
    # \u0590-\u05fe = range for hebrew characters
    re_goitein_section = re.compile(
        r" (?P<p>(\d+?[\u0590-\u05fe]|[\u0590-\u05fe]\d+)[\u0590-\u05fe]?)", flags=re.I
    )

    def parse_editor(self, document, editor, translation=False):
        # multiple editions are indicated by "; also ed."  or ". also ed."
        # split so we can parse each edition separately and add a footnote
        editions = re.split(r"[;.] (?=also ed\.|ed\.|also)", editor, flags=re.I)

        for i, edition in enumerate(editions):

            # check for transcription content
            transcription = self.transcriptions.get(str(document.pk))
            # check for and exclude empty content
            if transcription and transcription["lines"] == [""]:
                transcription = None

            # strip whitespace and periods before checking ignore list
            if edition.rstrip(" .").lower() in self.editor_ignore:
                # skip unless there is a transcription, in which case
                # we want to import it
                if not transcription:
                    continue

            # footnotes for these records are always editions
            doc_relation = {Footnote.EDITION}
            # if importing from translator column, also set translation
            if translation:
                doc_relation.add(Footnote.TRANSLATION)
            notes = []
            location = []
            # copy the edition text before removing any notes or
            # other information
            edition_text = edition

            # beginning usually includes indicator if edition or edition
            # or translation
            edit_transl_match = self.re_docrelation.match(edition)
            if edit_transl_match:
                # if doc relation text includes translation, set flag
                if "trans" in edit_transl_match.group(0).lower():
                    doc_relation.add(Footnote.TRANSLATION)

                # remove ed/trans from edition text
                edition_text = self.re_docrelation.sub("", edition_text)

            ed_notes_match = self.re_ed_notes.search(edition_text)
            if ed_notes_match:
                # save the notes to add to the footnote
                # remove from the edition before parsing
                edition_text = self.re_ed_notes.sub("", edition_text)
                notes.append(ed_notes_match.groupdict()["note"])

            # check for url and store if present
            url_match = self.re_url.search(edition)
            url = ""
            if url_match:
                # save the url, and remove from edition text, to simplify parsing
                url = url_match.group("url")
                edition_text = edition_text.replace(url, "").strip()

            # if reference includes document or page location,
            # remove and store for footnote location
            doc_match = self.re_doc_location.search(edition_text)
            if doc_match:
                location.append(doc_match.groupdict()["doc"])
                edition_text = self.re_doc_location.sub("", edition_text)
            page_match = self.re_page_location.search(edition_text)
            if page_match:
                location.append(page_match.groupdict()["pages"])
                edition_text = self.re_page_location.sub("", edition_text)
            gsection_match = self.re_goitein_section.search(edition_text)
            if gsection_match:
                location.append(gsection_match.groupdict()["p"])
                edition_text = self.re_goitein_section.sub("", edition_text)

            # remove any whitespace left after pulling out notes and location
            # and strip any trailing punctuation
            edition_text = edition_text.strip(" .,;")
            try:
                source = self.get_source(edition_text, document)
                fn = Footnote(
                    source=source,
                    content_object=document,
                    doc_relation=doc_relation,
                    location=", ".join(location),
                    url=url,
                    notes="\n".join(notes),
                )
                # if this is the first edition, check for a transcription based
                # on PGPID and attach it to the footnote
                if i == 0 and not translation:
                    fn.content = transcription
                fn.save()

            except KeyError as err:
                logger.error(
                    "Error parsing PGDID %d editor '%s': %s"
                    % (document.id, edition, err)
                )

    def get_source_creator(self, name):
        # last name is always present, and last names are unique
        lastname = name.rsplit(" ")[-1]
        try:
            return self.source_creators[lastname]
        except Exception:

            logger.error("Source creator not found for %s" % name)
            raise

    # upper or lower case volume, with or without period or space
    re_volume = re.compile(r"(, )?\bvol.? ?(?P<volume>\d+)", flags=re.I)

    # known journal titles/variants with optional volume
    # volume is usually numeric, but could also be ##.# or ##/##
    re_journal = re.compile(
        r"(?P<match>(?P<journal>Tarbiz|Zion|Genzei Qedem|Ginzei Qedem|"
        + r"Kiryat Sefer|Qiryat Sefer|Peʿamim|Peamim|"
        + r"(The )?Jewish Quarterly Review|JQR|Shalem|"
        + r"Bulletin of the School of Oriental and African Studies|BSOAS|"
        + r"Jewish History|Leshonenu|Eretz Israel|Aretz Israel|"
        + r"AJS Review|Dine Israel|Journal of Semitic Studies|Sinai|"
        + r"Qoveṣ al Yad|Kovetz al Yad|Te’udah|Te’uda|Sefunot|Sfunoth)"
        + r"(,? ?(Vol\.)? ?(?P<volume>\d[\d./]*))?)"
    )

    # known book titles for book sections
    re_book = re.compile(
        r"(?P<match>(?P<book>Otzar yehudey Sfarad|Yehoshua Finkel Festschrift|"
        + r"Joshua Finkel Festschrift|Gratz College Anniversary volume|"
        + r"Studies in Judaica, Karaitica and Islamica|Mas'at Moshe|"
        + r"Studi Orientalistic in onore di Levi Della Vida))",
        flags=re.U,
    )

    # check for language specified; languages are only Hebrew, German, and English
    # Hebrew sometimes occurs as Heb; Hebrew appers in both quotes and brackets
    re_language = re.compile(
        r"(?P<match>\(?(into)? [\[(]?(?P<lang>Heb(rew)?|German|English)[\])]?)([ ,.]|$)"
    )

    def get_source(self, edition, document):
        # parse the edition information and get the source for this scholarly
        # record if it already exists; if it doesn't, create it

        # create a list of text to add to notes
        note_lines = []  # notes probably apply to footnote, not source
        ed_orig = edition

        # set defaults for information that may not be present
        title = volume = language = location = journal = book = ""

        # if this is an ignored text, we are only here because there is
        # a transcription; create or find an anonymous entry, so the
        # footnote will be created and transcription can be attached
        unknown_check = edition.lower().strip().strip(".")
        if any([unknown_check.startswith(ignore) for ignore in self.editor_ignore]):
            return Source.objects.get_or_create(
                title="[unknown source]",
                source_type=self.source_types["Unpublished"],
                notes="Source of transcription not noted in original PGP database (or similar)",
            )[0]

        # check for url and store if present
        url_match = self.re_url.search(edition)
        url = ""
        if url_match:
            # save the url, and remove from edition text, to simplify parsing
            url = url_match.group("url")
            edition = edition.replace(url, "").strip()

        # check for 4-digit year and store it if present
        year = None
        # one record has a date range; others have a one or two digit month
        # match: #/#### or ##/### ; (####); , ####, ; ####-####
        # (exclude 4-digit years that occur in titles)
        year_match = re.search(
            r"\b(?P<match>(\d{4}[––]|\d{1,2}\/| ?\(|(?:, ))(?P<year>\d{4})([) ,.]|$))",
            edition,
        )
        if year_match:
            # store the year
            year = int(year_match.group("year"))
            # check full match against year; if they differ (i.e., includes month or year range)
            # add to notes
            full_match = year_match.group("match")
            edition = edition.replace(full_match, "").strip(" .,")
            # cleanup for comparison and potentially adding to notes
            full_match = full_match.strip("(), ")
            if full_match != str(year):
                note_lines.append(full_match)

        # check for known journal titles
        journal_match = self.re_journal.search(edition)
        if journal_match:
            # set journal and volume if found
            journal = journal_match.group("journal")
            volume = journal_match.group("volume") or ""
            # remove journal & volume from edition text
            edition = edition.replace(journal_match.group("match"), "")

        else:  # if no journal, check for separate volume number
            vol_match = self.re_volume.search(edition)
            # if found, store volume and remove from edition text
            if vol_match:
                volume = vol_match.group("volume")
                edition = self.re_volume.sub("", edition)

        # check for known book titles
        book_match = self.re_book.search(edition)
        if book_match:
            # set book title if found
            book = book_match.group("book")
            # remove from edition text
            edition = edition.replace(book_match.group("match"), "")

        # check for language
        lang_match = self.re_language.search(edition)
        if lang_match:
            language = lang_match.group("lang")
            if language == "Heb":
                language = "Hebrew"
            # remove from edition text
            edition = edition.replace(lang_match.group("match"), "")

        # no ea
        # but there are only a few instances
        special_cases = [
            "Lorenzo Bondioli, Tamer el-Leithy, Joshua Picard, Marina Rustow and Zain Shirazi",
            "Khan, el-Leithy, Rustow and Vanthieghem",
            "Oded Zinger, Naim Vanthieghem and Marina Rustow",
            "Allony, Ben-Shammai, Frenkel",
            "Allony, Ben-Shammai, and Frenkel",
        ]
        ed_parts = None
        for special_case in special_cases:
            # if special case matches, split manually on known names
            if edition.startswith(special_case):
                ed_parts = [edition[: len(special_case)], edition[len(special_case) :]]

        # if not a special case, split normally
        if not ed_parts:
            # split into chunks on commas, parentheses, brackets, semicolons
            ed_parts = [p.strip() for p in re.split(r"[,()[\];]", edition)]

        # authors always listed first
        author_names = re.split(r", | and | & ", ed_parts.pop(0))
        authors = []
        for author in author_names:
            # remove any trailing whitespace or periods
            author = author.strip(" .")
            if author:
                authors.append(self.get_source_creator(author))
            # warn if no authors? (likely an error)

        # if there are more parts, the second is the title
        if ed_parts:
            title = ed_parts.pop(0).strip()

        # determine source type
        if journal:  # if a journal title was found, type is article
            src_type = "Article"
        elif book:  # if a book title was found, type is book section
            src_type = "Book Section"
        elif "diss" in edition.lower() or "thesis" in edition.lower():
            src_type = "Dissertation"
        elif not title:
            src_type = "Unpublished"
        elif any(
            [
                term in edition
                for term in ["typed texts", "unpublished", "handwritten texts"]
            ]
        ):
            src_type = "Unpublished"
        # title with quotes indicates Article; straight or curly quotes
        elif title[0] in ["'", '"', "“", "‘"]:
            src_type = "Article"
        # if it isn't anything else, it's a book
        else:
            src_type = "Book"

        # strip any quotes from beginning and end of title
        # also strip periods and any whitespace
        title = title.strip("\"'”“‘’ .")

        # add any leftover pieces of the edition text to notes
        note_lines.extend(ed_parts)

        # look to see if this source already exists
        # (no title indicates pgp-only edition)
        extra_opts = {}
        # if there is no title and year is set or type is unpublished,
        # filter on year (whether set or not)
        if not title and (year or src_type == "Unpublished"):
            extra_opts["year"] = year

        # when multiple authors are present, we want to match *all* of them
        # filter on combination of last names AND total count
        author_filter = models.Q()
        author_count = len(authors)
        for a in authors:
            author_filter = author_filter & models.Q(authors__last_name=a.last_name)

        sources = (
            Source.objects.annotate(author_count=models.Count("authorship"))
            .filter(
                title__iexact=title,
                volume=volume,
                source_type__type=src_type,
                author_count=author_count,
                journal=journal or book,
                **extra_opts,
            )
            .filter(author_filter)
            .distinct()
        )

        if sources.count() > 1:
            logger.warn(
                "Found multiple sources for %s, title=%s journal=%s vol=%s year=%s (%s)"
                % (
                    "; ".join([a.last_name for a in authors]),
                    title,
                    journal,
                    volume,
                    year,
                    src_type,
                )
            )

        source = sources.first()
        if source:
            updated = False
            # set year if available and not already set
            if title and not source.year and year:
                source.year = year
                updated = True

            # if there is any *NEW* note information, add to existing notes

            if note_lines:
                new_notes = [
                    n
                    for n in note_lines
                    if not (n in source.other_info or n in source.notes)
                ]
                new_note_text = " ".join(new_notes)
                # if there are existing notes, combine
                if source.notes:
                    new_note_text = "\n".join([source.notes, new_note_text])
                source.notes = new_note_text
                updated = True

            # save changes if any were made
            if updated:
                source.save()

            # return the existing source for creating a footnote
            return source

        # existing source not found;create a new one!
        source = Source.objects.create(
            source_type=self.source_types[src_type],
            title=title,
            volume=volume,
            journal=journal or book,
            year=year,
            other_info=" ".join(note_lines),
            notes="\n".join(["Created from PGPID %s" % document.id] + note_lines),
        )
        # log source record creation
        self.log_creation(source)

        # associate language if specified
        if language:
            lang = SourceLanguage.objects.get(name=language)
            source.languages.add(lang)
        # associate authors
        self.add_source_authors(source, authors)

        # return for footnote creation
        return source

    def add_source_authors(self, source, authors):
        # add authors, preserving listed order
        for i, author in enumerate(authors, 1):
            source.authorship_set.create(creator=author, sort_order=i)
