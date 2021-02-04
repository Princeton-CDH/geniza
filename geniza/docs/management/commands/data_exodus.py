import codecs
import csv

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
import requests

from geniza.docs.models import Library


class Command(BaseCommand):
    'Import existing data from PGP spreadsheets into the database'

    logentry_message = 'Created via data exodus script'

    def handle(self, *args, **kwargs):
        script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        library_content_type = ContentType.objects.get_for_model(Library)

        # import list of libraries and abbreviations
        # TODO: csv file location should be configured in local settings

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
                user_id=script_user.id,
                content_type_id=library_content_type.pk,
                object_id=library.pk,
                object_repr=str(library),
                change_message=self.logentry_message,
                action_flag=ADDITION)

    def get_csv(self, name):
        # given a name for a file in the configured data import urls,
        # load the data by url and initialize and return a csv reader
        response = requests.get(settings.DATA_IMPORT_URLS[name],
                                stream=True)
        if response.status_code != requests.codes.ok:
            raise CommandError('Error accessing CSV for %s: %s' % (name, response))

        return csv.DictReader(codecs.iterdecode(response.iter_lines(),
                              'utf-8'))
