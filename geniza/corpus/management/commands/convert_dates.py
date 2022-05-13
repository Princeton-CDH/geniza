import csv

from django.core.management.base import BaseCommand, CommandError

from geniza.corpus.dates import Calendar, display_date_range, standardize_date
from geniza.corpus.models import Document


class Command(BaseCommand):
    """Report on historical date conversions for current data"""

    report_fields = [
        "pgpid",
        "doc_date_original",
        "doc_date_calendar",
        "doc_date_standard",
        "converted_date",
        "weekday",
        "error",
    ]

    def add_arguments(self, parser):
        #     parser.add_argument("mode", choices=["report", "merge"])
        parser.add_argument(
            "report-path", type=str, nargs="?", default="date-conversion-report.csv"
        )

    def handle(self, *args, **options):
        # NOTE: for now, this script only reports on date conversion
        # in future, will add an update mode to clean up and standardize
        # existing dates in the databse

        # find all documents with original dates set;
        # limit to calendars that we support converting
        dated_docs = Document.objects.exclude(
            doc_date_original="", doc_date_calendar=""
        ).filter(doc_date_calendar__in=Calendar.can_convert)

        with open(options["report-path"], "w") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(self.report_fields)

            for doc in dated_docs:
                error = converted_date = weekday = ""
                try:
                    converted_date = standardize_date(
                        doc.doc_date_original, doc.doc_date_calendar
                    )

                except ValueError as e:
                    error = str(e)  # report if error on conversion
                # if we have a single date, determine weekday and include in report
                if converted_date and converted_date[0] == converted_date[1]:
                    weekday = converted_date[0].strftime("%A")

                # output current and converted values in csv
                csvwriter.writerow(
                    [
                        doc.id,
                        doc.doc_date_original,
                        doc.get_doc_date_calendar_display(),
                        doc.doc_date_standard,
                        display_date_range(*converted_date) if converted_date else "",
                        weekday,
                        error,
                    ]
                )
