import csv

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

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
        parser.add_argument("mode", choices=["report", "update"])
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

        if options["mode"] == "report":
            self.report(dated_docs, options["report-path"])
        elif options["mode"] == "update":
            self.standardize_dates(dated_docs)

    def report(self, dated_docs, report_path):
        """Generate a CSV report of documents with dates and converted standard dates"""
        with open(report_path, "w") as csvfile:
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

    def standardize_dates(self, dated_docs):
        """Update documents with dates to standard format"""
        doc_contenttype = ContentType.objects.get_for_model(Document)
        script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # exclude documents with uncertain digits; looks like [..] or similar;
        # also exclude date ranges, which we don't yet support
        dated_docs = (
            dated_docs.exclude(doc_date_original__contains="[.")
            .exclude(doc_date_original__contains="–")
            .exclude(doc_date_original__contains="-")
        )
        updated = 0

        for doc in dated_docs:
            try:
                # standardize date, if possible
                converted_date = doc.standardize_date()
                # if it was successful, update if this is a change
                if converted_date:
                    doc.doc_date_standard = converted_date
                    if doc.has_changed("doc_date_standard"):
                        doc.save()
                        # create log entry documenting the change
                        LogEntry.objects.log_action(
                            user_id=script_user.id,
                            content_type_id=doc_contenttype.pk,
                            object_id=doc.pk,
                            object_repr=str(doc),
                            change_message="Recalculated standard document date",
                            action_flag=CHANGE,
                        )
                        updated += 1

            except ValueError as e:
                self.stdout.write(
                    self.style.WARNING(
                        "Error converting date for document %s: %s" % (doc.id, e)
                    )
                )

        self.stdout.write("Updated %d documents" % updated)
