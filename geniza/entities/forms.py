from dal import autocomplete, forward
from django import forms
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from geniza.common.fields import RangeField, RangeForm
from geniza.corpus.forms import BooleanFacetField, FacetChoiceField, YearRangeWidget
from geniza.entities.models import (
    Person,
    PersonDocumentRelationType,
    PersonEventRelation,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonRole,
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


class RelationTypeMergeFormMixin:
    def __init__(self, *args, **kwargs):
        ids = kwargs.get("ids", [])

        # Remove the added kwarg so that the super method doesn't error
        try:
            del kwargs["ids"]
        except KeyError:
            pass

        super().__init__(*args, **kwargs)
        self.fields[
            "primary_relation_type"
        ].queryset = self.reltype_model.objects.filter(id__in=ids)


class PersonDocumentRelationTypeChoiceField(forms.ModelChoiceField):
    """Add a summary of each PersonDocumentRelationType to a form (used for merging)"""

    label_template = get_template(
        "entities/snippets/persondocumentrelationtype_option_label.html"
    )

    def label_from_instance(self, relation_type):
        return self.label_template.render({"relation_type": relation_type})


class PersonDocumentRelationTypeMergeForm(RelationTypeMergeFormMixin, forms.Form):
    primary_relation_type = PersonDocumentRelationTypeChoiceField(
        label="Select primary person-document relationship",
        queryset=None,
        help_text=(
            "Select the primary person-document relationship, which will be "
            "used as the canonical entry. All associated relations and log "
            "entries will be combined on the primary relationship."
        ),
        empty_label=None,
        widget=forms.RadioSelect,
    )
    reltype_model = PersonDocumentRelationType


class PersonPersonRelationTypeChoiceField(forms.ModelChoiceField):
    """Add a summary of each PersonPersonRelationType to a form (used for merging)"""

    label_template = get_template(
        "entities/snippets/personpersonrelationtype_option_label.html"
    )

    def label_from_instance(self, relation_type):
        return self.label_template.render({"relation_type": relation_type})


class PersonPersonRelationTypeMergeForm(RelationTypeMergeFormMixin, forms.Form):
    primary_relation_type = PersonPersonRelationTypeChoiceField(
        label="Select primary person-person relationship",
        queryset=None,
        help_text=(
            "Select the primary person-person relationship, which will be "
            "used as the canonical entry. All associated relations and log "
            "entries will be combined on the primary relationship."
        ),
        empty_label=None,
        widget=forms.RadioSelect,
    )
    reltype_model = PersonPersonRelationType


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
            "to_person": autocomplete.ModelSelect2(
                url="entities:person-autocomplete",
                forward=(forward.Const(True, "is_person_person_form"),),
            ),
        }
        help_texts = {
            "to_person": "Please check auto-populated and manually-input people sections to ensure you are not entering the same relationship twice. If there is more than one relationship between the same two people, record the family relationship and add a note about the other relationship."
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


class PersonListForm(RangeForm):
    q = forms.CharField(
        label="Keyword or Phrase",
        required=False,
        widget=forms.TextInput(
            attrs={
                # Translators: placeholder for people keyword search input
                "placeholder": _("Search for people by name"),
                # Translators: accessible label for people keyword search input
                "aria-label": _("word or phrase"),
                "type": "search",
            }
        ),
    )
    gender = FacetChoiceField(label=_("Gender"))
    has_page = BooleanFacetField(label=_("Detail page available"))
    social_role = FacetChoiceField(label=_("Social role"))
    document_relation = FacetChoiceField(label=_("Relation to documents"))
    exclude_uncertain = BooleanFacetField(label=_("Exclude uncertain identifications"))
    # translators: label for person activity dates field
    date_range = RangeField(label=_("Dates"), required=False, widget=YearRangeWidget())

    SORT_CHOICES = [
        # Translators: label for sort by relevance
        ("relevance", _("Relevance")),
        # Translators: label for sort by name
        ("name", _("Name")),
        # Translators: label for sort by person activity dates
        ("date", _("Date")),
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

    # mapping of solr facet fields to form input
    solr_facet_fields = {
        "gender": "gender",
        "has_page": "has_page",
        "roles": "social_role",
        "document_relations": "document_relation",
        "certain_document_relations": "document_relation",
    }
    # mapping of solr facet fields to db models in order to retrieve objects by label
    solr_db_models = {
        "roles": PersonRole,
        "document_relations": PersonDocumentRelationType,
        "certain_document_relations": PersonDocumentRelationType,
    }

    def get_translated_label(self, field, label):
        """Lookup translated label via db model object when applicable;
        handle Person.gender as a special case; and otherwise just return the label"""
        db_model = self.solr_db_models.get(field, None)
        if db_model:
            # use objects_by_label to find original object and use translation
            return getattr(db_model, "objects_by_label").get(label, label)
        elif field == "gender":
            # gender is a ChoiceField with translated labels, keyed on first letter (M,F,U)
            gender_key = label[0]
            return dict(Person.GENDER_CHOICES)[gender_key]
        else:
            # not gender, can't find db field; just return label as-is
            return label

    def set_choices_from_facets(self, facets):
        """Set choices on field from a dictionary of facets"""
        # borrowed from ppa-django

        # show all or only certain doc relations, based on whether
        # exclude_uncertain has been checked
        if (
            self.is_valid()
            and self.cleaned_data.get("exclude_uncertain", False)
            and facets.get("document_relations", None)
        ):
            del facets["document_relations"]
        elif facets.get("certain_document_relations", None):
            del facets["certain_document_relations"]

        # populate facet field choices from current facets
        for key, facet_dict in facets.items():
            # restructure dict to set values of each key to tuples of (label, count)
            # labels should be translated, so use original object
            facet_dict = {
                label: (self.get_translated_label(key, label), count)
                for (label, count) in sorted(facet_dict.items())
            }
            # use field from facet fields map or else field name as is
            formfield = self.solr_facet_fields.get(key, key)
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
            return bool({k: v for k, v in self.cleaned_data.items() if bool(v)})
        return False


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


class PlaceListForm(forms.Form):
    SORT_CHOICES = [
        # Translators: label for sort by name
        ("name", _("Name")),
        # Translators: label for sort by number of related documents
        ("documents", _("Related Documents")),
        # Translators: label for sort by number of related people
        ("people", _("Related People")),
        # Translators: label for sort by relevance
        ("relevance", _("Relevance")),
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

    q = forms.CharField(
        label="Keyword or Phrase",
        required=False,
        widget=forms.TextInput(
            attrs={
                # Translators: placeholder for place keyword search input
                "placeholder": _("Search for places by name"),
                # Translators: accessible label for places keyword search input
                "aria-label": _("word or phrase"),
                "type": "search",
            }
        ),
    )

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
