import csv
from collections import namedtuple

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Given a CSV of fragments and IIIF URLs, add those IIIF urls to their respective fragments in the database"""

    def add_arguments(self, parser):
        parser.add_argument("-c", "--csv", type=str, required=True)
        parser.add_argument("-o", "--overwrite", action="store_true")

    def handle(self, *args, **options):
        self.csv_path = options.get("csv")
        self.overwrite = options.get("overwrite")

        self.get_iiif_csv()
        self.import_iiif_urls()

    def get_iiif_csv(self):
        # given a name for a file in the configured data import urls,
        # load the data by url and initialize and return a generator
        # of namedtuple elements for each row

        with open(self.csv_path) as f:
            csvreader = csv.reader(f)
            header = next(csvreader)

            # Create a namedtuple based on headers in the csv
            # and local mapping of csv names to access names
            CsvRow = namedtuple("IiifCsvRow", header)

            # iterate over csv rows and yield a generator of the namedtuple
            for row in csvreader:
                yield CsvRow(*row)

    def import_iiif_urls(self):
        pass
        # Get Fragment that matches shelfmark
        # Raise an warning if it does not exist (?)

        # if iif_url is None
        #   set iiif_url
        # elif overwrite
        #   set iiif_url
        #   log info: overwriting
