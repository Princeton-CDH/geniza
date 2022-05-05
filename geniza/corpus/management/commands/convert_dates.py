import csv

from django.core.management.base import BaseCommand, CommandError

from geniza.corpus.dates import (
    convert_hebrew_date,
    convert_islamic_date,
    display_date_range,
)
from geniza.corpus.models import Document


class Command(BaseCommand):
    """Report on date conversions for current data"""

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
        # find all documents with original dates set
        dated_docs = Document.objects.exclude(
            doc_date_original="", doc_date_calendar=""
        )
        # for now, limit to hebrew
        dated_docs = dated_docs.filter(
            doc_date_calendar__in=[Document.CALENDAR_ANNOMUNDI, Document.CALENDAR_HIJRI]
        )

        with open(options["report-path"], "w") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(self.report_fields)

            for doc in dated_docs:
                error = converted_date = weekday = ""
                try:
                    if doc.doc_date_calendar == Document.CALENDAR_ANNOMUNDI:
                        converted_date = convert_hebrew_date(doc.doc_date_original)
                    if doc.doc_date_calendar == Document.CALENDAR_HIJRI:
                        converted_date = convert_islamic_date(doc.doc_date_original)

                except ValueError as e:
                    error = str(e)  # report if error on conversion
                # print(
                #     "\nPGPID %s : %s   =   %s  | %s\n"
                #     % (doc.id, doc.doc_date_original, doc.doc_date_standard, converted_date)
                # )
                # if we have a single date, determine weekday and report
                if converted_date and converted_date[0] == converted_date[1]:
                    weekday = converted_date[0].strftime("%A")

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
