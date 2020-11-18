import csv
import pathlib

from django.core.management.base import BaseCommand, CommandParser
from geniza.people.models import Person


class Command(BaseCommand):
    """Imports a .csv of people's names. Expects a 'Name PGP' column from which 
    to read the name."""

    help = __doc__

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=str, help="path to .csv file")

    def handle(self, *args, **options) -> None:
        path = pathlib.Path(options["csv_file"])
        with path.open(encoding="utf8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                Person.objects.create(name=row["Name PGP"])
