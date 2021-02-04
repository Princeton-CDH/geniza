import csv

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from geniza.docs.models import Library


class Command(BaseCommand):
    'Import existing data from PGP spreadsheets into the database'

    logentry_message = 'Created via data exodus script'

    def handle(self, *args, **kwargs):
        script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        library_content_type = ContentType.objects.get_for_model(Library)

        # import list of libraries and abbreviations
        # TODO: csv file location should be configured in local settings
        with open('pgp_libraries.csv') as librarycsv:
            csvreader = csv.DictReader(librarycsv)

            # NOTE: because we're using postgres, we can use bulk
            # create and still get pks for the newly created items
            libraries = Library.objects.bulk_create([
                Library(name=row['Library'], abbrev=row['Abbreviation'])
                for row in csvreader if row['Library'] and row['Abbreviation']
            ])

            for library in libraries:
                LogEntry.objects.log_action(
                    user_id=script_user.id,
                    content_type_id=library_content_type.pk,
                    object_id=library.pk,
                    object_repr=str(library),
                    change_message=self.logentry_message,
                    action_flag=ADDITION)
