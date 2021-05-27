import csv
import re
import logging
from collections import namedtuple

from django.core.management.base import BaseCommand

from geniza.corpus.models import Fragment


# logging config: use levels as integers for verbosity option
logger = logging.getLogger("import")
logging.basicConfig()
LOG_LEVELS = {0: logging.ERROR, 1: logging.WARNING, 2: logging.INFO, 3: logging.DEBUG}


class Command(BaseCommand):
    """Given a CSV of fragments and IIIF URLs, add those IIIF urls to their respective fragments in the database"""

    def __init__(self, *args, **options):
        self.csv_path = options.get("csv")
        self.overwrite = options.get("overwrite")
        self.dryrun = options.get("dryrun")

    def add_arguments(self, parser):
        parser.add_argument("-c", "--csv", type=str, required=True)
        parser.add_argument("-o", "--overwrite", action="store_true")
        parser.add_argument("-d", "--dryrun", action="store_true")

    def handle(self, *args, **options):
        self.csv_path = options.get("csv")
        self.overwrite = options.get("overwrite")
        self.dryrun = options.get("dryrun")

        rows = self.get_iiif_csv()
        for row in rows:
            self.import_iiif_url(row)

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

    def view_to_iiif_url(self, url):
        iiif_link = url.replace("/view/", "/iiif/")
        # view links end with /1 or /2 but iiif link does not include it
        iiif_link = re.sub(r"/\d$", "", iiif_link)
        return iiif_link

    def import_iiif_url(self, row):
        try:
            fragment = Fragment.objects.get(shelfmark=row.shelfmark)
        except Fragment.DoesNotExist:
            # logger.warning(
            #     f"Fragment with shelfmark {row.shelfmark} does not exist in the database."
            # )
            return

        if not fragment.iiif_url or self.overwrite:
            fragment.iiif_url = self.view_to_iiif_url(row.url)

            if self.dryrun:
                logger.info(f"Set {fragment} url to {row.url}")
            else:
                fragment.save()
