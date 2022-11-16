from io import StringIO

import pytest
from django.core.management import call_command

from geniza.corpus.dates import Calendar
from geniza.corpus.management.commands import convert_dates


@pytest.mark.django_db
def test_convert_date_report(tmp_path, document, join):
    # add convertable dates to the documents
    document.doc_date_original = "507"
    document.doc_date_calendar = Calendar.HIJRI
    document.doc_date_standard = "1113"
    document.save()

    join.doc_date_original = "12 Elul 4968"
    join.doc_date_calendar = Calendar.ANNO_MUNDI
    join.doc_date_standard = "1208"
    join.save()

    stderr = StringIO()
    report_file = tmp_path / "date-conversion-report.csv"
    call_command("convert_dates", "report", str(report_file), stderr=stderr)

    with open(report_file) as f:
        lines = f.readlines()
    # header + two documents with convertable dates
    assert len(lines) == 3
    # documents ordered by pk, join is first
    assert join.doc_date_original in lines[1]
    assert join.get_doc_date_calendar_display() in lines[1]
    assert join.doc_date_standard in lines[1]
    assert document.doc_date_original in lines[2]
    assert document.get_doc_date_calendar_display() in lines[2]
    assert document.doc_date_standard in lines[2]
    # converted date
    assert "1208-08-26" in lines[1]
    assert "1113-06-18/1114-06-06" in lines[2]


@pytest.mark.django_db
def test_convert_date_standardize(document, join):
    # add convertable dates to the documents
    # - one we can handle
    document.doc_date_original = "507"
    document.doc_date_calendar = Calendar.HIJRI
    document.doc_date_standard = "1113"
    document.save()
    doc_logentry_count = document.log_entries.count()

    # one we can't handle
    join.doc_date_original = "First decade of Elul 4968"
    join.doc_date_calendar = Calendar.ANNO_MUNDI
    join.doc_date_standard = "1208"
    join.save()
    join_logentry_count = join.log_entries.count()

    stdout = StringIO()
    command = convert_dates.Command(stdout=stdout)
    command.handle(mode="update")

    # check that the first document has been updated
    document.refresh_from_db()
    assert document.doc_date_standard == "1113-06-18/1114-06-06"
    # check that a log entry was created
    assert document.log_entries.count() == doc_logentry_count + 1
    # check that the second document has not been updated
    join.refresh_from_db()
    assert join.log_entries.exists() == join_logentry_count
    output = stdout.getvalue()
    assert "Error converting date for document {}".format(join.id) in output
    assert "Updated 1 document" in output


@pytest.mark.django_db
def test_convert_date_clean(document, join):
    # add non-standard dates to clean up
    document.doc_date_standard = "1127–38"
    document.save()
    doc_logentry_count = document.log_entries.count()

    join.doc_date_standard = "1208/10/03"
    join.save()
    join_logentry_count = join.log_entries.count()

    stdout = StringIO()
    command = convert_dates.Command(stdout=stdout)
    command.handle(mode="clean")

    # check that the first document has been updated
    document.refresh_from_db()
    assert document.doc_date_standard == "1127/1138"
    # check that a log entry was created
    assert document.log_entries.count() == doc_logentry_count + 1
    # check that the second document has been updated
    join.refresh_from_db()
    assert join.doc_date_standard == "1208-10-03"
    assert join.log_entries.exists() == join_logentry_count + 1
    output = stdout.getvalue()
    assert "2 documents with invalid standardized dates" in output
    assert "Updated 2 documents" in output
