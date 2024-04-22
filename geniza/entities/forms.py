from dal import autocomplete
from django import forms
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from geniza.corpus.forms import FacetChoiceField
from geniza.entities.models import (
    Person,
    PersonDocumentRelationType,
    PersonPersonRelation,
    PersonPlaceRelation,
    PersonRole,
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


class PersonListForm(forms.Form):
    gender = FacetChoiceField(label=_("Gender"))
    social_role = FacetChoiceField(label=_("Social role"))
    document_relation = FacetChoiceField(label=_("Relation to documents"))

    SORT_CHOICES = [
        # Translators: label for sort by name
        ("name", _("Name")),
        # Translators: label for sort by person activity dates
        # ("date_desc", _("Date")),
        # Translators: label for sort by social role
        ("role", _("Social Role")),
        # Translators: label for sort by number of related documents
        ("documents", _("Related Documents")),
        # Translators: label for sort by number of related people
        ("people", _("Related People")),
        # Translators: label for sort by number of related places
        ("places", _("Related Places")),
    ]

    sort = forms.ChoiceField(
        # Translators: label for form sort field
        label=_("Sort by"),
        choices=SORT_CHOICES,
        required=False,
        widget=forms.RadioSelect,
    )

    SORT_DIR_CHOICES = [
        # Translators: label for ascending sort
        ("asc", _("Ascending")),
        # Translators: label for descending sort
        ("desc", _("Descending")),
    ]

    sort_dir = forms.ChoiceField(
        choices=SORT_DIR_CHOICES,
        required=False,
        widget=forms.RadioSelect,
    )

    # form field name aliases for faceted django queries
    facet_field_aliases = {
        "role__name": "social_role",
        "persondocumentrelation__type__name": "document_relation",
    }

    # dict of lambda functions to get (translated) labels for each facet field value
    label_accessors = {
        "gender": lambda k: dict(Person.GENDER_CHOICES)[k],
        "role__name": lambda k: str(
            PersonRole.objects_by_label.get(k, _("Unknown role"))
        ),
        "persondocumentrelation__type__name": lambda k: PersonDocumentRelationType.objects.get(
            name_en=k
        ).name,
    }

    def set_choices_from_facets(self, facets):
        """Set choices on field from a dictionary of facets"""
        # adapted from ppa-django;
        # populate facet field choices from current facets
        for key, facet_list in facets.items():
            # restructure dict to set values of each key to tuples of (label, count)
            facet_dict = {
                # since filter fields are not 1:1 mapped to django fields, use accessor
                # helper functions to get labels
                facet[key]: (self.label_accessors[key](facet[key]), facet["count"])
                for facet in facet_list
                if facet[key] is not None
            }
            formfield = self.facet_field_aliases.get(key, key)
            # for each facet, set the corresponding choice field
            if formfield in self.fields:
                self.fields[formfield].populate_from_facets(facet_dict)

    def get_sort_label(self):
        """Helper method to get the label for the current value of the sort field"""
        if (
            self.is_valid()
            and "sort" in self.cleaned_data
            and self.cleaned_data["sort"]
        ):
            raw_value = self.cleaned_data["sort"]
            return dict(self.SORT_CHOICES)[raw_value]
        return None

    def filters_active(self):
        """Check if any filters are active; returns true if form fields are set"""
        if self.is_valid():
            return bool(
                {
                    k: v
                    for k, v in self.cleaned_data.items()
                    if k not in ["sort", "sort_dir"] and bool(v)
                }
            )
        return False
