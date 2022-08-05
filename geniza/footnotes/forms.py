from dal import autocomplete
from django import forms
from django.contrib.contenttypes.forms import generic_inlineformset_factory

from geniza.footnotes.models import Footnote


class FootnoteInlineForm(forms.ModelForm):
    class Meta:
        model = Footnote
        exclude = ("content", "url", "location", "notes")
        widgets = {
            "source": autocomplete.ModelSelect2(url="corpus:source-autocomplete")
        }


FootnoteInlineFormSet = generic_inlineformset_factory(
    model=Footnote,
    form=FootnoteInlineForm,
    max_num=1,
    exclude=("content", "url", "doc_relation", "location", "notes"),
    can_delete=False,
)
