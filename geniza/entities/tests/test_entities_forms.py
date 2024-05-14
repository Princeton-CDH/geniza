from unittest.mock import Mock, patch

import pytest
from django.urls import reverse

from geniza.corpus.forms import FacetChoiceField
from geniza.entities.forms import PersonChoiceField, PersonListForm, PersonMergeForm
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


@pytest.mark.django_db
class TestPersonListForm:
    def test_set_choices_from_facets(self, person, person_diacritic):
        form = PersonListForm()
        with patch.object(FacetChoiceField, "populate_from_facets"):
            facets = {
                "gender": [
                    {"gender": Person.MALE, "count": 1},
                    {"gender": Person.FEMALE, "count": 2},
                ],
            }
            # should set labels and counts
            form.set_choices_from_facets(facets)
            form.fields["gender"].populate_from_facets.assert_called_with(
                {
                    Person.FEMALE: (person.get_gender_display(), 2),
                    Person.MALE: (person_diacritic.get_gender_display(), 1),
                }
            )
            # should get translated labels
            facets = {
                "role__name": [{"role__name": person.role.name_en, "count": 1}],
            }
            form.set_choices_from_facets(facets)
            form.fields["social_role"].populate_from_facets.assert_called_with(
                {person.role.name_en: (person.role.name, 1)}
            )

    def test_filters_active(self):
        # should correctly ascertain if filters are active
        form = PersonListForm({"gender": None})
        assert form.filters_active() == False
        form = PersonListForm({"gender": [Person.FEMALE]})
        assert form.filters_active() == True
        # sort should not count as a filter
        form = PersonListForm({"sort": "gender"})
        assert form.filters_active() == False

    def test_get_sort_label(self):
        form = PersonListForm({})
        assert form.get_sort_label() is None

        form = PersonListForm({"sort": "role"})
        assert form.get_sort_label() == dict(PersonListForm.SORT_CHOICES)["role"]
