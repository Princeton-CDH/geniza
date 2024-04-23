from dal import autocomplete
from django import forms
from django.template.loader import get_template

from geniza.entities.models import (
    Person,
    PersonEventRelation,
    PersonPersonRelation,
    PersonPlaceRelation,
    PlaceEventRelation,
    PlacePlaceRelation,
)


class PersonChoiceField(forms.ModelChoiceField):
    """Add a summary of each person to a form (used for person merging)"""

    label_template = get_template("entities/snippets/person_option_label.html")

    def label_from_instance(self, person):
        return self.label_template.render({"person": person})


class PersonMergeForm(forms.Form):
    primary_person = PersonChoiceField(
        label="Select primary person",
        queryset=None,
        help_text=(
            "Select the primary person, which will be used as the canonical person entry. "
            "All metadata, relationships (people/places/documents), footnotes, and log "
            "entries will be combined on the primary person."
        ),
        empty_label=None,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        person_ids = kwargs.get("person_ids", [])

        # Remove the added kwarg so that the super method doesn't error
        try:
            del kwargs["person_ids"]
        except KeyError:
            pass

        super().__init__(*args, **kwargs)
        self.fields["primary_person"].queryset = Person.objects.filter(
            id__in=person_ids
        )


class PersonPersonForm(forms.ModelForm):
    class Meta:
        model = PersonPersonRelation
        fields = (
            "to_person",
            "type",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "to_person": autocomplete.ModelSelect2(url="entities:person-autocomplete"),
        }


class PersonPlaceForm(forms.ModelForm):
    class Meta:
        model = PersonPlaceRelation
        fields = (
            "place",
            "type",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "place": autocomplete.ModelSelect2(url="entities:place-autocomplete"),
            "type": autocomplete.ModelSelect2(),
        }


class PlacePersonForm(forms.ModelForm):
    class Meta:
        model = PersonPlaceRelation
        fields = (
            "person",
            "type",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "person": autocomplete.ModelSelect2(url="entities:person-autocomplete"),
            "type": autocomplete.ModelSelect2(),
        }


class PlacePlaceForm(forms.ModelForm):
    class Meta:
        model = PlacePlaceRelation
        fields = (
            "place_b",
            "type",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "place_b": autocomplete.ModelSelect2(url="entities:place-autocomplete"),
            "type": autocomplete.ModelSelect2(),
        }


class EventPersonForm(forms.ModelForm):
    class Meta:
        model = PersonEventRelation
        fields = ("person", "notes")
        widgets = {
            "person": autocomplete.ModelSelect2(url="entities:person-autocomplete"),
            "notes": forms.Textarea(attrs={"rows": "4"}),
        }


class EventPlaceForm(forms.ModelForm):
    class Meta:
        model = PlaceEventRelation
        fields = ("place", "notes")
        widgets = {
            "place": autocomplete.ModelSelect2(url="entities:place-autocomplete"),
            "notes": forms.Textarea(attrs={"rows": "4"}),
        }


class EventForm(forms.ModelForm):
    class Meta:
        help_texts = {
            "automatic_date": "Date or date range automatically generated from associated document(s)"
        }
