from datetime import date

import convertdate
import pytest
from django.core.exceptions import ValidationError

from geniza.corpus.dates import (
    Calendar,
    PartialDate,
    convert_hebrew_date,
    convert_islamic_date,
    get_hebrew_month,
    get_islamic_month,
)
from geniza.corpus.models import Document


class TestDocumentDateMixin:
    # for convenience, use the Document model to test the date mixin

    def test_clean(self):
        doc = Document()
        # no dates; no error
        doc.clean()

        # original date but no calendar — error
        doc.doc_date_original = "480"
        with pytest.raises(ValidationError):
            doc.clean()

        # calendar but no date — error
        doc.doc_date_original = ""
        doc.doc_date_calendar = Calendar.HIJRI
        with pytest.raises(ValidationError):
            doc.clean()

        # both — no error
        doc.doc_date_original = "350"
        doc.clean()

    def test_original_date(self):
        """Should display the historical document date with its calendar name"""
        doc = Document(doc_date_original="507", doc_date_calendar=Calendar.HIJRI)
        assert doc.original_date == "507 Hijrī"
        # with no calendar, just display the date
        doc.doc_date_calendar = ""
        assert doc.original_date == "507"

    def test_standard_date(self):
        # no dates; no error
        doc = Document()
        assert doc.standard_date is None

        # single day
        doc.doc_date_standard = "1569-10-23"
        assert doc.standard_date == "23 October, 1569 CE"

        # date range
        doc.doc_date_standard = "1839-03-17/1840-03-04"
        assert doc.standard_date == "17 March, 1839 — 4 March, 1840 CE"

        # year/month
        doc.doc_date_standard = "1839-03"
        assert doc.standard_date == "March 1839 CE"

        # year only
        doc.doc_date_standard = "1839"
        assert doc.standard_date == "1839 CE"

        # fallback behavior for dates in the wrong format
        doc.doc_date_standard = "1029–38"
        assert doc.standard_date == "1029–38 CE"

    def test_document_date(self):
        """Should combine historical and converted dates"""
        doc = Document(
            doc_date_original="507",
            doc_date_calendar=Calendar.HIJRI,
        )
        # should just use the original_date method
        assert doc.document_date == doc.original_date
        # should wrap standard date in parentheses and add CE
        doc.doc_date_standard = "1113/1114"
        assert (
            doc.document_date == "<span>507 Hijrī</span> <span>(1113 — 1114 CE)</span>"
        )
        # should return standard date only, no parentheses
        doc.doc_date_original = ""
        doc.doc_date_calendar = ""
        assert doc.document_date == "1113 — 1114 CE"

    def test_standardize_date(self):
        doc = Document()
        # no dates, nothing done
        assert doc.standardize_date() is None
        # unsupported calendar, nothing done
        doc.doc_date_original = "507"
        doc.doc_date_calendar = Calendar.KHARAJI
        assert doc.standardize_date() is None

        # supported calendar, no update
        doc.doc_date_calendar = Calendar.HIJRI
        standardized = doc.standardize_date()
        assert standardized is not None
        # check converted to detailed display form
        assert standardized == "1113-06-18/1114-06-06"
        # not set without update requested
        assert doc.doc_date_standard == ""

        # update requested, should update
        standardized = doc.standardize_date(update=True)
        assert doc.doc_date_standard == standardized

    def test_solr_date_range(self):
        doc = Document()
        # no dates, returns none
        assert doc.solr_date_range() is None
        # single date returned as-is
        doc.doc_date_standard = "1839-03-17"
        assert doc.solr_date_range() == "1839-03-17"
        # date range converted to solr format
        doc.doc_date_standard = "1839-03-17/1840-03-04"
        assert doc.solr_date_range() == "[1839-03-17 TO 1840-03-04]"


# test hebrew date conversion
def test_get_hebrew_month():
    # month name used in the convertdate library
    assert get_hebrew_month("Kislev") == convertdate.hebrew.KISLEV
    # local override
    assert get_hebrew_month("Tishrei") == convertdate.hebrew.TISHRI


def test_convert_hebrew_date():
    # single day, gregorian
    converted_date = convert_hebrew_date("5 Elul 5567")
    # start/end should be the same
    assert converted_date[0] == converted_date[1]
    # expected converted date
    assert converted_date[1] == date(1807, 9, 8)

    # single day, julian
    converted_date = convert_hebrew_date("Thursday, 16 Elul 5[2]09")
    # start/end should be the same
    assert converted_date[0] == converted_date[1]
    # expected converted date
    assert converted_date[1] == date(1449, 9, 4)

    # month/year
    converted_date = convert_hebrew_date("Tishrei 4898")
    # expect 1137-09-18/1137-10-17
    assert converted_date[0] == date(1137, 9, 18)
    assert converted_date[1] == date(1137, 10, 17)

    # year only
    converted_date = convert_hebrew_date("5632")
    # should be 1871/1872
    assert converted_date[0].year == 1871
    assert converted_date[1].year == 1872
    # hebrew civil calendar begins in Tishri, in September
    assert converted_date[0] == date(1871, 9, 16)
    assert converted_date[1] == date(1872, 10, 2)

    # season is currently ignored
    converted_date = convert_hebrew_date("spring 5632")
    # should be the same as year only
    assert converted_date[0] == date(1871, 9, 16)
    assert converted_date[1] == date(1872, 10, 2)


# test islamic date conversion
def test_get_islamic_month():
    # month name as used in the convertdate library
    assert get_islamic_month("Rajab") == 7  # referenced by number, no defines
    # month name without accents
    assert get_islamic_month("Safar") == 2
    # local override
    assert get_islamic_month("Muharram") == 1
    assert get_islamic_month("Dhū l-Qaʿda") == 11


def test_convert_islamic_date():
    # single day
    converted_date = convert_islamic_date("Tuesday, 27 Dhū l-Qaʿda 632")
    # start/end should be the same
    assert converted_date[0] == converted_date[1]
    # expected converted date
    assert converted_date[1] == date(1235, 8, 13)

    # year/month
    converted_date = convert_islamic_date("Rajab 495")
    # expect 1102-04-21/1102-05-20
    assert converted_date[0] == date(1102, 4, 21)
    assert converted_date[1] == date(1102, 5, 20)

    # year only
    converted_date = convert_islamic_date("441")
    # should be 1049/1050
    assert converted_date[0].year == 1049
    assert converted_date[1].year == 1050
    # 1049-06-05/1050-05-25
    assert converted_date[0] == date(1049, 6, 5)
    assert converted_date[1] == date(1050, 5, 25)


def test_partialdate():
    # single day
    assert str(PartialDate("1569-10-23")) == "23 October, 1569"

    # month/year
    assert str(PartialDate("1569-10")) == "October 1569"

    # year only
    assert str(PartialDate("1569")) == "1569"

    # raise value error for too many parts
    with pytest.raises(ValueError):
        PartialDate("1569-10-23-24")

    with pytest.raises(ValueError):
        PartialDate("1569--10-23")
