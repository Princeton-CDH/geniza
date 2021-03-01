import codecs
import csv
import re
from collections import namedtuple

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

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
    }
}

# named tuple for CSV fields in library spreadsheet
# LibraryRow = namedtuple('LibraryCollection', (
#     'current',  # Current List of Libraries
#     'library',  # Library
#     'abbrev',   # Abbreviation
#     'location',  # Location (current)
#     'collection'  # Collection (if different from library)
# ))


class Command(BaseCommand):
    'Import existing data from PGP spreadsheets into the database'

    logentry_message = 'Created via data import script'

    library_lookup = {}
    document_type = {}

    def setup(self):
        if not hasattr(settings, 'DATA_IMPORT_URLS'):
            raise CommandError('Please configure DATA_IMPORT_URLS in local settings')

        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

    def handle(self, *args, **kwargs):
        self.setup()
        self.import_collections()
        self.import_languages()
        # self.import_documents()

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
            csv_fields[name].get(col, col.lower()) for col in header
        ))

        # iterate over csv rows and yield a generator of the namedtuple
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
            LogEntry.objects.log_action(
                user_id=self.script_user.id,
                content_type_id=language_content_type.pk,
                object_id=lang.pk,
                object_repr=str(lang),
                change_message=self.logentry_message,
                action_flag=ADDITION)

        self.stdout.write('Imported %d languages' % len(languages))

    def import_documents(self):
        metadata = self.get_csv('metadata')
        Document.objects.all().delete()
        Fragment.objects.all().delete()

        for row in metadata:
            if ';' in row['Type']:
                print('skipping PGPID %s (demerge)' % row['PGPID'])
                continue

            doctype = self.get_doctype(row['Type'])
            fragment = self.get_fragment(row)
            doc = Document.objects.create(
                id=row['PGPID'],
                doctype=doctype,
                description=row['Description'],
                old_input_by=row['Input by (optional)'],
                old_input_date=row['Date entered (optional)']
            )
            doc.fragments.add(fragment)
            doc.tags.add(*[tag.strip() for tag in
                         row['Tags'].split('#') if tag.strip()])
            # associate fragment via text block
            TextBlock.objects.create(
                document=doc,
                fragment=fragment,
                # TODO: convert recto/verso value to code!
                side=row['Recto or verso (optional)'],
                extent_label=row['Text-block (optional)']
            )
            # TODO: language/script; needs mapping
            # joins

            # TODO: handle joins on a second pass?
            # so fragments will already exist if referenced directly
            if row['Joins']:
                join_shelfmarks = set(row['Joins'].strip().split(' + '))
                try:
                    join_shelfmarks.remove(row['Shelfmark - Current'])
                except KeyError:
                    print('key error for %s / %s' % (row['PGPID'], row['Shelfmark - Current']))
                print('join_shelfmarks')
                print(join_shelfmarks)

                for shelfmark in join_shelfmarks:
                    join_fragment = Fragment.objects.filter(shelfmark=shelfmark).first()
                    if not join_fragment:
                        print('!! join fragment %s doesn\'t exist' % shelfmark)
                    # create stub fragment
                    # add textblock

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
        shelfmark = data.get('Shelfmark - Current', None)
        if not shelfmark:
            # warn? shouldn't be missing
            return
        fragment = Fragment.objects.filter(shelfmark=shelfmark).first()
        if fragment:
            # check against current values and warn if mismatch?
            return fragment

        # if fragment was not found, create it
        fragment = Fragment.objects.create(
            shelfmark=shelfmark,
            # todo: handle missing libraries (set from shelfmark?)
            collection=self.library_lookup.get(data['Library'].strip(), None),
            old_shelfmarks=data['Shelfmark - Historical (optional)'],
            multifragment=data['Multifragment (optional)'],
            url=data['Link to image'],
            iiif_url=self.get_iiif_url(data)
        )
        # TODO: logentry to document creation or update
        return fragment

    def get_iiif_url(self, data):
        '''Get IIIF Manifest URL for a fragment when possible'''

        # cambridge iiif manifest links use the same id as view links
        # NOTE: should exclude search link like this one:
        # https://cudl.lib.cam.ac.uk/search?fileID=&keyword=T-s%2013J33.12&page=1&x=0&y=
        extlink = data['Link to image']
        if 'cudl.lib.cam.ac.uk/view/' in extlink:
            iiif_link = extlink.replace('/view/', '/iiif/')
            # view links end with /1 or /2 but iiif link does not include it
            iiif_link = re.sub(r'/\d$', '', iiif_link)
            return iiif_link

        # TODO: get new figgy iiif urls for JTS images based on shelfmark
        # if no url, return empty string for blank instead of null
        return ''
