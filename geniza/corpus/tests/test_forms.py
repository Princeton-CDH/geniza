import itertools
from unittest.mock import Mock, patch

import pytest
from django import forms
from django.db.models import Count
from taggit.models import Tag

from geniza.corpus.forms import (
    CheckboxSelectWithCount,
    DocumentChoiceField,
    DocumentMergeForm,
    DocumentSearchForm,
    FacetChoiceField,
    FacetChoiceSelectField,
    SelectWithCount,
    SelectWithDisabled,
    TagChoiceField,
    TagMergeForm,
)
from geniza.corpus.models import Document, DocumentType


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


class TestFacetChoiceSelectField:
    # similar to FacetChoiceField, but slightly different formatting and using a Select widget

    def test_init(self):
        fcf = FacetChoiceSelectField()
        assert not fcf.empty_label
        fcf = FacetChoiceSelectField(empty_label="Select...")
        assert fcf.empty_label == "Select..."
        # uses SelectWithCount
        assert fcf.widget.__class__ == SelectWithCount
        # not required by default
        assert not fcf.required
        # still can override required with a kwarg
        fcf = FacetChoiceField(required=True)
        assert fcf.required

    def test_populate_from_facets(self):
        fcf = FacetChoiceSelectField()
        # should format like "label (count)"
        fcf.populate_from_facets({"example": ("label", 1)})
        assert fcf.choices == [
            ("example", '<span>label</span> (<span class="count">1</span>)')
        ]
        # should add a choice with the empty label if provided
        fcf = FacetChoiceSelectField(empty_label="Select...")
        fcf.populate_from_facets({"example": ("label", 1)})
        assert len(fcf.choices) == 2
        assert ("", "Select...") in fcf.choices


class TestDocumentSearchForm:
    # test adapted from ppa-django

    def test_init(self):
        data = {"q": "illness"}
        # has query, relevance enabled
        form = DocumentSearchForm(data)
        assert form.fields["sort"].widget.choices[0] == form.SORT_CHOICES[0]
        assert form.fields["translation_language"].disabled == True

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

        data = {"q": "illness", "has_translation": True}
        form = DocumentSearchForm(data)
        assert form.fields["translation_language"].disabled == False

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
        fake_facets = {"type": {"foo": 1, "bar": 2, "baz": 3}}
        # mock doctype objects by label cached property
        with patch.object(DocumentType, "objects_by_label") as mock_doctype_obj_dict:
            # populate two of the three facets with labeled objects
            foo = DocumentType(name_en="foo_label")
            bar = DocumentType(name_en="bar_label")
            mock_dict = {"foo": foo, "bar": bar}
            mock_doctype_obj_dict.get.side_effect = mock_dict.get
            form.set_choices_from_facets(fake_facets)
            context = form.fields["doctype"].widget.get_context(
                "doctype", "all", {"id": "id_doctype"}
            )
            # collect all 3 facets
            optgroup = [
                *context["widget"].get("optgroups", [])[0][1],
                *context["widget"].get("optgroups", [])[1][1],
                *context["widget"].get("optgroups", [])[2][1],
            ]
            for option in optgroup:
                # should pass count to attrs
                if option["value"] in fake_facets["type"]:
                    count = fake_facets["type"].get(option["value"])
                    assert int(option["attrs"]["data-count"]) == count
                # should get label for foo and bar
                if option["value"] in ["foo", "bar"]:
                    assert "_label" in option["label"]
                # should fallback to Unknown type label for baz
                else:
                    assert "Unknown type" in option["label"]

    def test_boolean_checkbox_get_context(self):
        form = DocumentSearchForm()
        fake_facets = {"has_transcription": {"true": 10, "false": 2}}
        form.set_choices_from_facets(fake_facets)
        context = form.fields["has_transcription"].widget.get_context(
            "has_transcription", "all", {"id": "id_has_transcription"}
        )
        count = fake_facets["has_transcription"].get("true")
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

    def test_clean__regex(self):
        """test special validation for malformed regex searches"""

        form = DocumentSearchForm()
        bad_queries = [
            # malformed { queries
            ["{", "{}", ".{", "{1}", "{.+}"],
            # malformed * queries
            ["**", "*", ".**", "*.", "*a"],
            # malformed + queries
            ["++", "+", ".++", "+.", "+a"],
            # malformed <> queries
            ["<a>", "<a", "<", ".*<", "(?<!a)b"],
            # malformed "invalid character class" queries
            ["\\a", "\\b", "\\B", "\\r", "\\t", "\\3"],
        ]
        for q in itertools.chain.from_iterable(bad_queries):
            form.cleaned_data = {"mode": "regex", "q": q}
            form.clean()
            assert len(form.errors) == 1

        form = DocumentSearchForm()
        good_queries = [
            # good { queries
            [".{1}", "\\{", "\\{.+\\}"],
            # good * queries
            [".*", "a*", "\\**", "\\*."],
            # good + queries
            [".+", "a+", "\\++", "\\+."],
            # good <> queries
            ["\\<a\\>", "\\<a", "\\<", ".*\\<"],
            # fixed "invalid character class" queries
            ["\\\\a", "\\\\b", "\\\\B", "\\\\r", "\\\\t", "\\\\3"],
            # other good escape sequences
            ["\\d", "\\D", "\\s", "\\w"],
        ]
        for q in itertools.chain.from_iterable(good_queries):
            form.cleaned_data = {"mode": "regex", "q": q}
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


@pytest.mark.django_db
class TestTagChoiceField:
    def test_label_from_instance(self, document):
        # create tag, add to document, construct annotated queryset
        tag = Tag.objects.create(name="example tag")
        document.tags.add(tag)
        qs = Tag.objects.filter(pk=tag.pk).annotate(
            item_count=Count("taggit_taggeditem_items", distinct=True),
        )

        # Should incldue tag name and count in label
        tag_choice_field = TagChoiceField(Mock())
        label = tag_choice_field.label_from_instance(qs.first())
        assert str(tag.name) in label
        assert "(1 tagged)" in label


class TestTagMergeForm:
    @pytest.mark.django_db
    def test_init(self):
        # no error if tag ids not specified
        TagMergeForm()

        # create test tag records
        Tag.objects.create(name="example tag1")
        Tag.objects.create(name="tag2")
        Tag.objects.create(name="example3")

        # initialize with ids for all but the last
        tags = Tag.objects.all().order_by("pk")
        tag_ids = list(tags.values_list("id", flat=True))
        mergeform = TagMergeForm(tag_ids=tag_ids[:-1])
        # total should have all but one tag
        assert mergeform.fields["primary_tag"].queryset.count() == tags.count() - 1
        # last tag should not be an available choice
        assert tags.last() not in mergeform.fields["primary_tag"].queryset
        # queryset should be annotated with counts
        assert all(
            hasattr(record, "item_count")
            for record in mergeform.fields["primary_tag"].queryset
        )
        assert mergeform.fields["primary_tag"].queryset.first().item_count == 0
