import csv
import pathlib

from django.core.management.base import BaseCommand, CommandParser
from geniza.people.models import Profession


class Command(BaseCommand):
    """Imports a .csv of professions. Expects columns for localized versions in
    Arabic and Judeo-Arabic, along with Occupation and Definition."""

    help = __doc__

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=str, help="path to .csv file")

    def handle(self, *args, **options) -> None:
        path = pathlib.Path(options["csv_file"])
        with path.open(encoding="utf8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                Profession.objects.create(
                    title_en=row["Occupation"],
                    title_ar=row["Arabic"],
                    title_he=row["Judeo-Arabic"],
                    description=row["Definition"]
                )
