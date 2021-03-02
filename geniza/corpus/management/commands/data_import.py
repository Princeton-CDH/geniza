import codecs
import csv
import re
from collections import namedtuple

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
        'Abbreviation': 'abbrev',
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

    library_lookup = {}
    document_type = {}
    language_lookup = {}  # this is provisional, assumes one language -> script mapping

    def setup(self):
        if not hasattr(settings, 'DATA_IMPORT_URLS'):
            raise CommandError('Please configure DATA_IMPORT_URLS in local settings')

        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

    def handle(self, *args, **kwargs):
        self.setup()
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
        if name == 'metadata':
            for row in list(csvreader)[:500]:
                yield CsvRow(*row)
        else:
            for row in csvreader:
                yield CsvRow(*row)

    def import_collections(self):
        collection_content_type = ContentType.objects.get_for_model(Collection)

        # clear out any existing collections
        Collection.objects.all().delete()
        # import list of libraries and abbreviations
        # convert to list so we can iterate twice
        library_data = list(self.get_csv('libraries'))

        # create a collection entry for every row in the sheet with both
        # required values
        collections = Collection.objects.bulk_create([
            Collection(library=row.library, abbrev=row.abbrev,
                       location=row.location,
                       collection=row.collection)
            for row in library_data if row.library and row.abbrev
        ])
        # NOTE: because we're using postgres, we can use bulk
        # create and still get pks for the newly created items

        # create log entries to document when & how records were created
        for coll in collections:
            LogEntry.objects.log_action(
                user_id=self.script_user.id,
                content_type_id=collection_content_type.pk,
                object_id=coll.pk,
                object_repr=str(coll),
                change_message=self.logentry_message,
                action_flag=ADDITION)

        self.stdout.write('Imported %d collections' % len(collections))

        # lookup for collection object by abbreviation
        lib_abbrev = {lib.abbrev: lib for lib in collections}
        # create a lookup for library as listed in the spreadsheet
        # mapping to newly created library object
        self.library_lookup = {
            row.current: lib_abbrev[row.abbrev]
            for row in library_data if row.abbrev and row.current}

    def import_languages(self):
        language_content_type = ContentType.objects.get_for_model(LanguageScript)

        LanguageScript.objects.all().delete()
        language_data = self.get_csv('languages')
        languages = LanguageScript.objects.bulk_create([
            LanguageScript(language=row.language,
                           script=row.script)
            for row in language_data if row.language and row.script
        ])

        # log all new objects
        for lang in languages:
            # Add to lookup for document import
            self.language_lookup[lang.language] = lang
            LogEntry.objects.log_action(
                user_id=self.script_user.id,
                content_type_id=language_content_type.pk,
                object_id=lang.pk,
                object_repr=str(lang),
                change_message=self.logentry_message,
                action_flag=ADDITION)

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

            # remove parentheticals and question marks
            lang = re.sub(r'\(.+\)', '', lang).replace('some', '').strip('? ')
            

            lang_model = self.language_lookup.get(lang)
            if not lang_model:
                print(f'ERROR language not found. PGPID: {row.pgpid}, Language: {lang}')
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
        for row in metadata:
            if ';' in row.type:
                print('skipping PGPID %s (demerge)' % row.pgpid)
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

            if row.joins.strip():
                joins.append((doc, row.joins))

        for doc, join in joins:
            shelfmarks = join.strip().split(' + ')
            existing_shelfmark = doc.shelfmark
            for shelfmark in shelfmarks:
                if shelfmark != existing_shelfmark:
                    join_fragment = Fragment.objects.filter(shelfmark=shelfmark).first()
                    if not join_fragment:
                        join_fragment = Fragment.objects.create(shelfmark=shelfmark)
                    doc.fragments.add(join_fragment)
        print(f'Imported {len(joins)} joins')

    doctype_lookup = {}

    def get_doctype(self, dtype):
        doctype = self.doctype_lookup.get(dtype, None)
        # if not yet in our local lookup, get from the db
        if not doctype:
            doctype = DocumentType.objects.get_or_create(name=dtype)[0]
            self.doctype_lookup[dtype] = doctype

        return doctype

    def get_fragment(self, data):
        # get the fragment for this document if it already exists;
        # if it doesn't, create it
        fragment = Fragment.objects.filter(shelfmark=data.shelfmark).first()
        if fragment:
            # check against current values and warn if mismatch?
            return fragment

        # if fragment was not found, create it
        fragment = Fragment.objects.create(
            shelfmark=data.shelfmark,
            # todo: handle missing libraries (set from shelfmark?)
            collection=self.library_lookup.get(data.library.strip(), None),
            old_shelfmarks=data.shelfmark_historic,
            multifragment=data.multifragment,
            url=data.image_link,
            iiif_url=self.get_iiif_url(data)
        )
        # TODO: logentry to document creation or update
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
