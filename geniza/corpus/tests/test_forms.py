from django import forms

from geniza.corpus.forms import (
    DocumentSearchForm,
    FacetChoiceField,
    RadioSelectWithCount,
    SelectWithDisabled,
)


class TestSelectedWithDisabled:
    # test adapted from ppa-django/mep-django

    class SampleForm(forms.Form):
        """Build a test form use the widget"""

        CHOICES = (
            ("no", {"label": "no select", "disabled": True}),
            ("yes", "yes can select"),
        )

        yes_no = forms.ChoiceField(choices=CHOICES, widget=SelectWithDisabled)

    def test_create_option(self):
        form = self.SampleForm()
        rendered = form.as_p()
        # no is disabled
        assert '<option value="no" disabled="disabled"' in rendered
        assert '<option value="yes">' in rendered


class TestFacetChoiceField:
    # test adapted from ppa-django

    def test_init(self):
        fcf = FacetChoiceField(legend="Document type")
        # uses RadioSelectWithCount
        fcf.widget == RadioSelectWithCount
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
                assert option["attrs"]["data-count"] == fake_facets["doctype"].get(
                    option["value"]
                )
            else:
                assert option["value"] == "all"
