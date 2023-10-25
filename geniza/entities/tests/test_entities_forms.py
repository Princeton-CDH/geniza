from unittest.mock import Mock

import pytest

from geniza.entities.forms import PersonChoiceField, PersonMergeForm
from geniza.entities.models import Name, Person


class TestPersonChoiceField:
    @pytest.mark.django_db
    def test_label_from_instance(self):
        # adapted from TestDocumentChoiceField
        choicefield = PersonChoiceField(Mock())

        # Should not error on a person with the most minimal information
        minimal = Person.objects.create()
        label = choicefield.label_from_instance(minimal)
        assert str(minimal.id) in label

        # Check that the attributes of a person are in label
        person = Person.objects.create()
        Name.objects.create(name="S.D. Goitein", content_object=person, primary=True)
        label = choicefield.label_from_instance(person)
        assert "S.D. Goitein" in label


class TestPersonMergeForm:
    @pytest.mark.django_db
    def test_init(self):
        # adapted from TestDocumentMergeForm

        # no error if person ids not specified
        PersonMergeForm()

        # create test person records
        Person.objects.bulk_create([Person(), Person(), Person(), Person()])
        # initialize with ids for all but the last
        people = Person.objects.all().order_by("pk")
        pids = list(people.values_list("id", flat=True))
        mergeform = PersonMergeForm(person_ids=pids[:-1])
        # total should have all but one person
        assert mergeform.fields["primary_person"].queryset.count() == people.count() - 1
        # last person should not be an available choice
        assert people.last() not in mergeform.fields["primary_person"].queryset
