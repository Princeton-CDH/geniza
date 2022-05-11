from abc import abstractclassmethod

import pytest
from django.core.exceptions import ValidationError

from geniza.corpus.dates import Calendar
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

    def test_document_date(self):
        """Should combine historical and converted dates"""
        doc = Document(
            doc_date_original="507",
            doc_date_calendar=Calendar.HIJRI,
        )
        # should just use the original_date method
        assert doc.document_date == doc.original_date
        # should wrap standard date in parentheses and add CE
        doc.doc_date_standard = "1113/14"
        assert doc.document_date == "507 Hijrī (1113/14 CE)"
        # should return standard date only, no parentheses
        doc.doc_date_original = ""
        doc.doc_date_calendar = ""
        assert doc.document_date == "1113/14 CE"
