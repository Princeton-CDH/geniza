import re
from unittest.mock import Mock

import pytest
from django import forms

from geniza.corpus.forms import (
    CheckboxSelectWithCount,
    DocumentChoiceField,
    DocumentMergeForm,
    DocumentSearchForm,
    FacetChoiceField,
    RadioSelectWithDisabled,
)
from geniza.corpus.models import Document


class TestSelectedWithDisabled:
    # test adapted from ppa-django/mep-django

    class SampleForm(forms.Form):
        """Build a test form use the widget"""

        CHOICES = (
            ("no", {"label": "no select", "disabled": True}),
            ("yes", "yes can select"),
        )

        yes_no = forms.ChoiceField(choices=CHOICES, widget=RadioSelectWithDisabled)

    def test_create_option(self):
        form = self.SampleForm()
        rendered = form.as_p()
        # no is disabled
        no_input = re.search(
            r"\<[ A-Za-z0-9\=\"\_\-]+value=\"no\"[ A-Za-z0-9\=\"\_\-]+>", rendered
        )
        yes_input = re.search(
            r"\<[ A-Za-z0-9\=\"\_\-]+value=\"yes\"[ A-Za-z0-9\=\"\_\-]+>", rendered
        )
        assert 'disabled="disabled"' in no_input.group()
        assert 'disabled="disabled"' not in yes_input.group()


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

    def test_choices_from_facets(self):
        """A facet dict should produce correct choice labels"""
        fake_facets = {"doctype": {"foo": 1, "bar": 2, "baz": 3}}
        form = DocumentSearchForm()
        # call the method to configure choices based on facets
        form.set_choices_from_facets(fake_facets)
        for choice in form.fields["doctype"].widget.choices:
            # choice is index id, label
            choice_label = choice[1]
            assert isinstance(choice_label, str)
            assert "<span>" in choice_label

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
                assert int(option["attrs"]["data-count"]) == fake_facets["doctype"].get(
                    option["value"]
                )

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
        assert str(footnote.source) in label
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
