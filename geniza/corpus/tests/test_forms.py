import re

from django import forms

from geniza.corpus.forms import (
    CheckboxSelectWithCount,
    DocumentSearchForm,
    FacetChoiceField,
    RadioSelectWithDisabled,
)


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
