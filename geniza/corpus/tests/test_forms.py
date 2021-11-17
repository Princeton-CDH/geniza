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
