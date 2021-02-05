import codecs
import csv

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
import requests

from geniza.corpus.models import Library


class Command(BaseCommand):
    'Import existing data from PGP spreadsheets into the database'

    logentry_message = 'Created via data exodus script'

    def setup(self):
        if not hasattr(settings, 'DATA_IMPORT_URLS'):
            raise CommandError('Please configure DATA_IMPORT_URLS in local settings')

        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

    def handle(self, *args, **kwargs):
        self.setup()
        self.import_libraries()

    def get_csv(self, name):
        # given a name for a file in the configured data import urls,
        # load the data by url and initialize and return a csv reader
        csv_url = settings.DATA_IMPORT_URLS.get(name, None)
        if not csv_url:
            raise CommandError('Import URL for %s is not configured' % name)
        response = requests.get(csv_url, stream=True)
        if response.status_code != requests.codes.ok:
            raise CommandError('Error accessing CSV for %s: %s' %
                               (name, response))

        return csv.DictReader(codecs.iterdecode(response.iter_lines(),
                              'utf-8'))

    def import_libraries(self):
        library_content_type = ContentType.objects.get_for_model(Library)

        # clear out any existing libraries
        Library.objects.all().delete()
        # import list of libraries and abbreviations
        library_data = self.get_csv('libraries')
        # create a Library entry for every row in the sheet with both
        # required values
        libraries = Library.objects.bulk_create([
            Library(name=row['Library'], abbrev=row['Abbreviation'])
            for row in library_data if row['Library'] and row['Abbreviation']
        ])
        # NOTE: because we're using postgres, we can use bulk
        # create and still get pks for the newly created items

        # create log entries to document when & how records were created
        for library in libraries:
            LogEntry.objects.log_action(
                user_id=self.script_user.id,
                content_type_id=library_content_type.pk,
                object_id=library.pk,
                object_repr=str(library),
                change_message=self.logentry_message,
                action_flag=ADDITION)
