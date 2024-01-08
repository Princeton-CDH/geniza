"""
Script to add catalog numbers to historical shelfmarks for some Bodleian
records. This is a one-time script and should be removed after the import is
completed in production.

Intended to be run manually from the shell as follows:
./manage.py add_cat_numbers historical_shelfmarks.csv
"""

import csv
import re

from django.core.management.base import BaseCommand

from geniza.corpus.models import Fragment


class Command(BaseCommand):
    """Import catalog numbers into Fragment records in the local database."""

    bodl_regex = r"^Bodl\. MS Heb\. (?P<letter>[A-Za-z]) (?P<num>\d+),"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to a CSV file")

    def handle(self, *args, **kwargs):
        with open(kwargs.get("path"), newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                cat_number = row["catalog no. (Bodl. historical shelfmarks)"]
                if cat_number:
                    try:
                        frag = Fragment.objects.get(pk=int(row["id"]))
                    except Fragment.DoesNotExist:
                        print(f"Error: cannot find fragment with id {row['id']}")
                        continue

                    # Bodl. MS heb. b 12/6
                    # --> data migration --> Bodl. MS Heb. b 12, f. 6
                    # --> this script --> Bodl. MS Heb. b 12 (Cat. 2875), f. 6
                    print(frag.old_shelfmarks)

                    hist_repl = (
                        f"Bodl. MS Heb. \g<letter> \g<num> (Cat. {cat_number}),",
                    )
                    hist = re.sub(self.bodl_regex, hist_repl, frag.old_shelfmarks)
                    frag.old_shelfmarks = hist

                    print(hist)

                    frag.save()
