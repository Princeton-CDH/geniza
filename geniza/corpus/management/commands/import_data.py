import codecs
import csv
import logging
import re
import os
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
from django.db import connection
from django.utils.text import slugify
from django.utils.timezone import get_current_timezone, make_aware

from geniza.corpus.models import (Collection, Document, DocumentType, Fragment,
                                  LanguageScript, TextBlock)

# mapping for csv header fields and local name we want to use
# if not specified, column will be lower-cased
csv_fields = {
    'libraries': {
        'Current List of Libraries': 'current',
        'Library abbreviation': 'lib_abbrev',
        'Collection abbreviation': 'abbrev',
        'Location (current)': 'location',
        'Collection (if different from library)': 'collection'
    },
    'languages': {
        # lower case for each should be fine
    },
    'metadata': {
        'Shelfmark - Current': 'shelfmark',
        'Input by (optional)': 'input_by',
        'Date entered (optional)': 'date_entered',
        'Recto or verso (optional)': 'recto_verso',
        'Language (optional)': 'language',
        'Text-block (optional)': 'text_block',
        'Shelfmark - Historical (optional)': 'shelfmark_historic',
        'Multifragment (optional)': 'multifragment',
        'Link to image': 'image_link',
    }
}

# events in document edit history with missing/malformed dates will replace
# missing portions with values from this date
DEFAULT_EVENT_DATE = datetime(2020, 1, 1)

# logging config: use levels as integers for verbosity option
logger = logging.getLogger("import")
logging.basicConfig()
LOG_LEVELS = {
    0: logging.ERROR,
    1: logging.WARNING,
    2: logging.INFO,
    3: logging.DEBUG
}


class Command(BaseCommand):
    'Import existing data from PGP spreadsheets into the database'

    logentry_message = 'Imported via script'

    content_types = {}
    collection_lookup = {}
    document_type = {}
    language_lookup = {}
    user_lookup = {}
    max_documents = None

    def add_arguments(self, parser):
        parser.add_argument('-m', '--max_documents', type=int)

    def setup(self, *args, **options):
        if not hasattr(settings, 'DATA_IMPORT_URLS'):
            raise CommandError(
                'Please configure DATA_IMPORT_URLS in local settings')

        # setup logging; default to WARNING level
        verbosity = options.get("verbosity", 1)
        logger.setLevel(LOG_LEVELS[verbosity])

        # load fixure containing known historic users (all non-active)
        call_command("loaddata", "historic_users",
                     app_label="corpus", verbosity=0)
        logger.info("loaded 30 historic users")

        # ensure current active users are present, but don't try to create them
        # in a test environment because it's slow and requires VPN access
        active_users = ["rrichman", "mrustow", "ae5677", "alg4"]
        if "PYTEST_CURRENT_TEST" not in os.environ:
            present = User.objects.filter(username__in=active_users) \
                                  .values_list("username", flat=True)
            for username in set(active_users) - set(present):
                call_command("createcasuser", username, staff=True,
                             verbosity=verbosity)

        # fetch users created through migrations for easy access later; add one
        # known exception (accented character)
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.team_user = User.objects.get(username=settings.TEAM_USERNAME)
        self.user_lookup["Naim Vanthieghem"] = User.objects.get(
            username="nvanthieghem")

        self.content_types = {
            model: ContentType.objects.get_for_model(model)
            for model in [Fragment, Collection, Document, LanguageScript]
        }

    def handle(self, *args, **options):
        self.setup(*args, **options)
        self.max_documents = options.get("max_documents")
        self.import_collections()
        self.import_languages()
        self.import_documents()

    def get_csv(self, name):
        # given a name for a file in the configured data import urls,
        # load the data by url and initialize and return a generator
        # of namedtuple elements for each row
        csv_url = settings.DATA_IMPORT_URLS.get(name, None)
        if not csv_url:
            raise CommandError('Import URL for %s is not configured' % name)
        response = requests.get(csv_url, stream=True)
        if response.status_code != requests.codes.ok:
            raise CommandError('Error accessing CSV for %s: %s' %
                               (name, response))

        csvreader = csv.reader(codecs.iterdecode(response.iter_lines(),
                                                 'utf-8'))
        header = next(csvreader)
        # Create a namedtuple based on headers in the csv
        # and local mapping of csv names to access names
        CsvRow = namedtuple('%sCSVRow' % name, (
            csv_fields[name].get(
                col,
                slugify(col).replace('-', '_') or 'empty_%d' % i)
            for i, col in enumerate(header)
            # NOTE: allows one empty header; more will cause an error
        ))

        # iterate over csv rows and yield a generator of the namedtuple
        for count, row in enumerate(csvreader, start=1):
            yield CsvRow(*row)
            # if max documents is configured, bail out for metadata
            if self.max_documents and name == 'metadata' and \
               count >= self.max_documents:
                break

    def import_collections(self):
        # clear out any existing collections
        Collection.objects.all().delete()
        # import list of libraries and abbreviations
        # convert to list so we can iterate twice
        library_data = list(self.get_csv('libraries'))

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
                    name=row.collection)
                collections.append(new_collection)

                # add the new object to library lookup
                # special case: CUL has multiple collections which use the
                # same library code in the metadata spreadsheet;
                # include collection abbreviation in lookup
                lookup_code = row.current
                if row.current == 'CUL':
                    lookup_code = '%s_%s' % (row.current, row.abbrev)
                self.collection_lookup[lookup_code] = new_collection

        # create log entries to document when & how records were created
        self.log_creation(*collections)
        logger.info('Imported %d collections' % len(collections))

    def import_languages(self):
        LanguageScript.objects.all().delete()
        language_data = self.get_csv('languages')
        languages = []
        for row in language_data:
            # skip empty rows
            if not row.language and not row.script:
                continue

            lang = LanguageScript.objects.create(
                language=row.language,
                script=row.script,
                display_name=row.display_name or None)

            # populate lookup for associating documents & languages;
            # use lower case spreadsheet name if set, or display name
            if row.display_name or row.spreadsheet_name:
                self.language_lookup[(row.spreadsheet_name or
                                      row.display_name).lower()] = lang
            languages.append(lang)

        # create log entries
        self.log_creation(*languages)
        logger.info('Imported %d languages' % len(languages))

    def add_document_language(self, doc, row):
        '''Parse languages and set probable_language and language_notes'''
        notes_list = []
        if not row.language:
            return

        for lang in row.language.split(';'):
            lang = lang.strip()
            # Place language in the language note if there're any non-question
            # mark notes in language entry
            if re.search(r'\([^?]+\)', lang):
                notes_list.append(lang)
            is_probable = '?' in lang
            # remove parentheticals, question marks, "some"
            lang = re.sub(r'\(.+\)', '', lang).replace('some', '').strip('? ')

            lang_model = self.language_lookup.get(lang.lower())
            if not lang_model:
                logger.error(
                    f'language not found. PGPID: {row.pgpid}, Language: {lang}')
            else:
                if is_probable:
                    doc.probable_languages.add(lang_model)
                else:
                    doc.languages.add(lang_model)

        if notes_list:
            doc.language_note = '\n'.join(notes_list)
            doc.save()

    def import_documents(self):
        metadata = self.get_csv('metadata')
        Document.objects.all().delete()
        Fragment.objects.all().delete()
        LogEntry.objects.filter(
            content_type_id=self.content_types[Document].id).delete()

        # create a reverse lookup for recto/verso labels used in the
        # spreadsheet to the codes used in the database
        recto_verso_lookup = {
            label.lower(): code
            for code, label in TextBlock.RECTO_VERSO_CHOICES
        }

        joins = []
        docstats = defaultdict(int)
        for row in metadata:
            if ';' in row.type:
                logger.warning('skipping PGPID %s (demerge)' % row.pgpid)
                docstats['skipped'] += 1
                continue

            doctype = self.get_doctype(row.type)
            fragment = self.get_fragment(row)
            doc = Document.objects.create(
                id=row.pgpid,
                doctype=doctype,
                description=row.description,
            )
            doc.tags.add(*[tag.strip() for tag in
                           row.tags.split('#') if tag.strip()])
            # associate fragment via text block
            TextBlock.objects.create(
                document=doc,
                fragment=fragment,
                # convert recto/verso value to code
                side=recto_verso_lookup.get(row.recto_verso, ''),
                extent_label=row.text_block,
                multifragment=row.multifragment
            )
            self.add_document_language(doc, row)
            docstats['documents'] += 1
            # create log entries as we go
            self.log_edit_history(doc, self.get_edit_history(row.input_by,
                                                             row.date_entered,
                                                             row.pgpid))

            # keep track of any joins to handle on a second pass
            if row.joins.strip():
                joins.append((doc, row.joins.strip()))

        # handle joins collected on the first pass
        for doc, join in joins:
            initial_shelfmark = doc.shelfmark
            for shelfmark in join.split(' + '):
                # skip the initial shelfmark, already associated
                if shelfmark == initial_shelfmark:
                    continue
                # get the fragment if it already exists
                join_fragment = Fragment.objects.filter(
                    shelfmark=shelfmark).first()
                # if not, create a stub fragment record
                if not join_fragment:
                    join_fragment = Fragment.objects.create(
                        shelfmark=shelfmark)
                    self.log_creation(join_fragment)
                # associate the fragment with the document
                doc.fragments.add(join_fragment)

        # update id sequence based on highest imported pgpid
        self.update_document_id_sequence()
        logger.info(
            'Imported %d documents, %d with joins; skipped %d' %
            (docstats['documents'], len(joins), docstats['skipped']))

    doctype_lookup = {}

    def get_doctype(self, dtype):
        # don't create an empty doctype
        if not dtype.strip():
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
        if lib_code == 'CUL':
            for cul_collection in ['T-S', 'CUL Or.', 'CUL Add.']:
                if data.shelfmark.startswith(cul_collection):
                    lib_code = 'CUL_%s' % cul_collection.replace('CUL ', '')
                    break
            # if code is still CUL, there is a problem
            if lib_code == 'CUL':
                logger.warning(
                    'CUL collection not determined for %s'
                    % data.shelfmark)
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
            iiif_url=self.get_iiif_url(data)
        )
        # log object creation
        self.log_creation(fragment)
        return fragment

    def get_iiif_url(self, data):
        '''Get IIIF Manifest URL for a fragment when possible'''

        # cambridge iiif manifest links use the same id as view links
        # NOTE: should exclude search link like this one:
        # https://cudl.lib.cam.ac.uk/search?fileID=&keyword=T-s%2013J33.12&page=1&x=0&y=
        extlink = data.image_link
        if 'cudl.lib.cam.ac.uk/view/' in extlink:
            iiif_link = extlink.replace('/view/', '/iiif/')
            # view links end with /1 or /2 but iiif link does not include it
            iiif_link = re.sub(r'/\d$', '', iiif_link)
            return iiif_link

        # TODO: get new figgy iiif urls for JTS images based on shelfmark
        # if no url, return empty string for blank instead of null
        return ''

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
                action_flag=ADDITION)

    def get_user(self, name, pgpid=None):
        """Find a user account based on a provided name, using a simple cache.

        If not found, tries to use first/last initials for lookup. If all else
        fails, use the generic team account (TEAM_USERNAME).
        """

        # check the cache first
        user = self.user_lookup.get(name)
        if user:
            logger.debug(
                f"using cached user {user} for {name} on PGPID {pgpid}")
            return user

        # person with given name(s) and last name – case-insensitive lookup
        if " " in name:
            given_names, last_name = [sname.strip(punctuation) for sname in
                                      name.rsplit(" ", 1)]
            try:
                user = User.objects.get(first_name__iexact=given_names,
                                        last_name__iexact=last_name)
            except User.DoesNotExist:
                pass

        # initials; use first & last to do lookup
        elif name:
            name = name.strip(punctuation)
            first_i, last_i = name[0], name[-1]
            try:
                user = User.objects.get(first_name__startswith=first_i,
                                        last_name__startswith=last_i)
            except User.DoesNotExist:
                pass

        # if we didn't get anyone through either method, warn and use team user
        if not user:
            logger.warning(
                f"couldn't find user {name} on PGPID {pgpid}; using {self.team_user}")
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
        all_input = map(str.strip, input_by.split(";"))
        all_dates = map(str.strip, date_entered.split(";"))

        # try to map every "input by" listing to a user account. for coauthored
        # events, add both users to a list – otherwise it's a one-element list
        # with the single user
        users = []
        for input_by in all_input:
            users.append([self.get_user(u, pgpid)
                          for u in input_by.split(" and ")])

        # convert every "date entered" listing to a date object. if any parts of
        # the date are missing, fill with default values below. for details:
        # https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.parse
        dates = []
        for date in all_dates:
            try:
                dates.append(parse(date, default=DEFAULT_EVENT_DATE).date())
            except ParserError:
                logger.warning(f"failed to parse date {date} on PGPID {pgpid}")
        dates.sort()

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
        for i, date in enumerate(reversed(dates)):

            # earliest date is creation; all others are revisions
            event_type = CHANGE if i < len(dates) - 1 else ADDITION

            # if we have a date without a user, assign to the whole team
            user = users[i] or (self.team_user,)

            # create events with this date and type for all the matching users.
            # if there was more than one user (coauthor), use the same type and
            # date to represent the coauthorship
            for u in user:
                events.append({"type": event_type, "user": u, "date": date})
            if len(user) > 1:
                logger.debug(
                    f"found coauthored event for PGPID {pgpid}: {events[-2:]}")
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
            dt = datetime(year=event["date"].year,
                          month=event["date"].month,
                          day=event["date"].day)
            msg = self.sheet_add_msg if event["type"] == ADDITION else self.sheet_chg_msg
            LogEntry.objects.create(
                user=event["user"],                            # FK in django
                content_type=self.content_types[Document],     # FK in django
                object_id=str(doc.pk),         # TextField in django
                object_repr=str(doc)[:200],    # CharField with limit in django
                change_message=msg,
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
            action_flag=ADDITION
        )

    def update_document_id_sequence(self):
        # set postgres document id sequence to maximum imported pgpid
        cursor = connection.cursor()
        cursor.execute(
            "SELECT setval('corpus_document_id_seq', max(id)) FROM corpus_document;")

