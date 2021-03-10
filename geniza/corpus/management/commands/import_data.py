import codecs
import csv
import re
from collections import defaultdict, namedtuple

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

import requests

from geniza.corpus.models import Collection, Document, DocumentType, Fragment,\
    LanguageScript, TextBlock

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


class Command(BaseCommand):
    'Import existing data from PGP spreadsheets into the database'

    logentry_message = 'Created via data import script'

    content_types = {}
    collection_lookup = {}
    document_type = {}
    language_lookup = {}  # this is provisional, assumes one language -> script mapping
    max_documents = None

    def add_arguments(self, parser):
        parser.add_argument('-m', '--max_documents', type=int)

    def setup(self):
        if not hasattr(settings, 'DATA_IMPORT_URLS'):
            raise CommandError('Please configure DATA_IMPORT_URLS in local settings')

        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.content_types = {
            model: ContentType.objects.get_for_model(model)
            for model in [Fragment, Collection, Document, LanguageScript]
        }

    def handle(self, max_documents=None, *args, **kwargs):
        self.setup()
        self.max_documents = max_documents
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
            csv_fields[name].get(col, slugify(col).replace('-', '_') or 'empty')
            for col in header
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
        self.stdout.write('Imported %d collections' % len(collections))

    def import_languages(self):
        LanguageScript.objects.all().delete()
        language_data = self.get_csv('languages')
        languages = LanguageScript.objects.bulk_create([
            LanguageScript(language=row.language,
                           script=row.script)
            for row in language_data if row.language and row.script
        ])

        # create log entries
        self.log_creation(*languages)
        # create lookup for associating documents & languages
        # NOTE: this lookup is provisional
        self.language_lookup = {lang.language: lang
                                for lang in languages}
        self.stdout.write('Imported %d languages' % len(languages))

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

            lang_model = self.language_lookup.get(lang)
            if not lang_model:
                self.stdout.write(
                    f'ERROR language not found. PGPID: {row.pgpid}, Language: {lang}')
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
                self.stdout.write('skipping PGPID %s (demerge)' % row.pgpid)
                docstats['skipped'] += 1
                continue

            doctype = self.get_doctype(row.type)
            fragment = self.get_fragment(row)
            doc = Document.objects.create(
                id=row.pgpid,
                doctype=doctype,
                description=row.description,
                old_input_by=row.input_by,
                old_input_date=row.date_entered
            )
            doc.tags.add(*[tag.strip() for tag in
                           row.tags.split('#') if tag.strip()])
            # associate fragment via text block
            TextBlock.objects.create(
                document=doc,
                fragment=fragment,
                # convert recto/verso value to code
                side=recto_verso_lookup.get(row.recto_verso, ''),
                extent_label=row.text_block
            )
            self.add_document_language(doc, row)
            docstats['documents'] += 1
            # create log entries as we go
            self.log_creation(doc)

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
                join_fragment = Fragment.objects.filter(shelfmark=shelfmark).first()
                # if not, create a stub fragment record
                if not join_fragment:
                    join_fragment = Fragment.objects.create(shelfmark=shelfmark)
                    self.log_creation(join_fragment)
                # associate the fragment with the document
                doc.fragments.add(join_fragment)

        self.stdout.write(
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
                self.stdout.write(self.style.WARNING(
                    'CUL collection not determined for %s'
                    % data.shelfmark))
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
            # TODO: handle CUL — two collections, same current code in metadata
            collection=self.get_collection(data),
            old_shelfmarks=data.shelfmark_historic,
            multifragment=data.multifragment,
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
