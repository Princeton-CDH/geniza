from django import forms
from django.template.loader import get_template

from geniza.entities.models import Person


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
