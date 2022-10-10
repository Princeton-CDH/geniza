from unittest.mock import Mock

import pytest
from django import forms

from geniza.corpus.forms import (
    CheckboxSelectWithCount,
    DocumentChoiceField,
    DocumentMergeForm,
    DocumentSearchForm,
    FacetChoiceField,
    SelectWithDisabled,
)
from geniza.corpus.models import Document


class TestSelectedWithDisabled:
    # test adapted from ppa-django/mep-django

    class MyTestForm(forms.Form):
        """Build a test form use the widget"""

        CHOICES = (
            ("no", {"label": "no select", "disabled": True}),
            ("yes", "yes can select"),
        )

        yes_no = forms.ChoiceField(choices=CHOICES, widget=SelectWithDisabled)

    def test_create_option(self):
        form = self.MyTestForm()
        rendered = form.as_p()
        print(rendered)
        # no is disabled
        assert '<option value="no" disabled="disabled"' in rendered
        assert '<option value="yes">' in rendered


class TestFacetChoiceField:
    # test adapted from ppa-django

    def test_init(self):
        fcf = FacetChoiceField(legend="Document type")
        # uses RadioSelectWithCount
        fcf.widget == CheckboxSelectWithCount
        # not required by default
        assert not fcf.required
        # still can override required with a kwarg
        fcf = FacetChoiceField(required=True)
        assert fcf.required

    def test_valid_value(self):
        fcf = FacetChoiceField()
        # valid_value should return true
        assert fcf.valid_value("foo")


class TestDocumentSearchForm:
    # test adapted from ppa-django

    def test_init(self):
        data = {"q": "illness"}
        # has query, relevance enabled
        form = DocumentSearchForm(data)
        assert form.fields["sort"].widget.choices[0] == form.SORT_CHOICES[0]

        # empty query, relevance disabled
        data["q"] = ""
        form = DocumentSearchForm(data)
        assert form.fields["sort"].widget.choices[0] == (
            "relevance",
            {"label": "Relevance", "disabled": True},
        )

        # no query, also relevance disabled
        del data["q"]
        form = DocumentSearchForm(data)
        assert form.fields["sort"].widget.choices[0] == (
            "relevance",
            {"label": "Relevance", "disabled": True},
        )

    def test_choices_from_facets(self):
        """A facet dict should produce correct choice labels"""
        fake_facets = {
            "doctype": {"foo": 1, "bar": 2, "baz": 3},
            "has_transcription": {"true": 3, "false": 3},
        }
        form = DocumentSearchForm()
        # call the method to configure choices based on facets
        form.set_choices_from_facets(fake_facets)
        # test doctype facets (FacetChoiceField)
        for choice in form.fields["doctype"].widget.choices:
            # choice is index id, label
            choice_label = choice[1]
            assert isinstance(choice_label, str)
            assert "<span>" in choice_label
        # test has_transcription facet (BooleanFacetField)
        bool_label = form.fields["has_transcription"].label
        assert isinstance(bool_label, str)
        assert "3</span>" in bool_label

    def test_radio_select_get_context(self):
        form = DocumentSearchForm()
        fake_facets = {"doctype": {"foo": 1, "bar": 2, "baz": 3}}
        form.set_choices_from_facets(fake_facets)
        context = form.fields["doctype"].widget.get_context(
            "doctype", "all", {"id": "id_doctype"}
        )
        optgroup = context["widget"].get("optgroups", [])[0][1]
        for option in optgroup:
            if option["value"] in fake_facets["doctype"]:
                (label, count) = fake_facets["doctype"].get(option["value"])
                assert int(option["attrs"]["data-count"]) == count

    def test_boolean_checkbox_get_context(self):
        form = DocumentSearchForm()
        fake_facets = {"has_transcription": {"true": 10, "false": 2}}
        form.set_choices_from_facets(fake_facets)
        context = form.fields["has_transcription"].widget.get_context(
            "has_transcription", "all", {"id": "id_has_transcription"}
        )
        (label, count) = fake_facets["has_transcription"].get("true")
        assert int(context["widget"]["attrs"]["data-count"]) == count

    def test_clean(self):
        """Should add an error if query is empty and sort is relevance"""
        form = DocumentSearchForm()
        form.cleaned_data = {"q": "", "sort": "relevance"}
        form.clean()
        assert len(form.errors) == 1

        # Otherwise should not raise an error
        form = DocumentSearchForm()
        form.cleaned_data = {"q": "test", "sort": "relevance"}
        form.clean()
        assert len(form.errors) == 0
        form = DocumentSearchForm()
        form.cleaned_data = {"q": "", "sort": "scholarship_desc"}
        form.clean()
        assert len(form.errors) == 0

    def test_clean_q(self):
        form = DocumentSearchForm()
        form.cleaned_data = {}
        # no error if keyword not set
        assert form.clean_q() is None
        # empty string should also be ok
        form.cleaned_data["q"] = ""
        assert form.clean_q() == ""

        # exact phrase with curly quotes
        form.cleaned_data["q"] = "“awaiting description”"
        assert form.clean_q() == '"awaiting description"'

    def test_filters_active(self):
        # no filters should return false
        form = DocumentSearchForm(data={"q": "test", "sort": "scholarship_desc"})
        assert not form.filters_active()
        # errors should return false
        form = DocumentSearchForm(
            data={"q": "", "sort": "relevance", "has_transcription": True}
        )
        assert not form.filters_active()
        # filters on, should return true
        form = DocumentSearchForm(data={"has_transcription": True})
        assert form.filters_active()
        # multivalue filter, should return true
        form = DocumentSearchForm(data={"doctype": ["Literary", "Paraliterary"]})
        assert form.filters_active()


class TestDocumentChoiceField:
    def test_label_from_instance(self, document, footnote):
        dchoicefield = DocumentChoiceField(Mock())

        # Should not error on a document with the most minimal information
        minimal_doc = Document.objects.create()
        label = dchoicefield.label_from_instance(minimal_doc)
        assert str(minimal_doc.id) in label

        # Check that the attributes of a document are in label
        document.footnotes.add(footnote)
        label = dchoicefield.label_from_instance(document)
        "Deed of sale" in label
        assert "Edition" in label
        "URL" not in label  # Ensure that the URL is not displayed when there is no URL


class TestDocumentMergeForm:
    @pytest.mark.django_db
    def test_init(self):
        # no error if document ids not specified
        DocumentMergeForm()

        # create test document records
        Document.objects.bulk_create([Document(), Document(), Document(), Document()])
        # initialize with ids for all but the last
        docs = Document.objects.all().order_by("pk")
        doc_ids = list(docs.values_list("id", flat=True))
        mergeform = DocumentMergeForm(document_ids=doc_ids[:-1])
        # total should have all but one document
        assert mergeform.fields["primary_document"].queryset.count() == docs.count() - 1
        # last document should not be an available choice
        assert docs.last() not in mergeform.fields["primary_document"].queryset

    @pytest.mark.django_db
    def test_clean(self):
        """Should add an error if rationale is 'other' and rationale notes are empty"""
        doc = Document.objects.create()

        form = DocumentMergeForm()
        form.cleaned_data = {
            "primary_document": doc.id,
            "rationale": "other",
            "rationale_notes": "",
        }
        form.clean()
        assert len(form.errors) == 1

        # should not produce an error if rationale notes provided
        form = DocumentSearchForm()
        form.cleaned_data = {
            "primary_document": doc.id,
            "rationale": "other",
            "rationale_notes": "test",
        }
        form.clean()
        assert len(form.errors) == 0

        # should not produce an error if rational is "duplicate" or "join"
        form = DocumentSearchForm()
        form.cleaned_data = {
            "primary_document": doc.id,
            "rationale": "duplicate",
            "rationale_notes": "",
        }
        form.clean()
        assert len(form.errors) == 0
