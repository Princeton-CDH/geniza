from dal import autocomplete
from django import forms

from geniza.footnotes.models import Source


class SourceChoiceForm(forms.Form):
    source = forms.ModelChoiceField(
        queryset=Source.objects.all().order_by("authors__last_name"),
        widget=autocomplete.ModelSelect2(url="corpus:source-autocomplete"),
    )
