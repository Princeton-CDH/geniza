from django import forms

from geniza.corpus.forms import DocumentSearchForm, SelectWithDisabled


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


class TestDocumentSearch:
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
