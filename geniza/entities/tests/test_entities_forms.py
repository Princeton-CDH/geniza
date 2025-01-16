from unittest.mock import Mock, patch

import pytest
from django.utils.translation import activate, get_language

from geniza.corpus.forms import FacetChoiceField
from geniza.entities.forms import (
    PersonChoiceField,
    PersonDocumentRelationTypeMergeForm,
    PersonListForm,
    PersonMergeForm,
    PlaceListForm,
)
from geniza.entities.models import Name, Person, PersonDocumentRelationType, PersonRole


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


class TestPersonDocumentRelationTypeMergeForm:
    @pytest.mark.django_db
    def test_init(self):
        # adapted from TestPersonMergeForm

        # no error if ids not specified
        PersonDocumentRelationTypeMergeForm()

        # create test records
        PersonDocumentRelationType.objects.bulk_create(
            [PersonDocumentRelationType(name=f"test{i}") for i in range(4)]
        )
        # initialize with ids for all but the last
        types = PersonDocumentRelationType.objects.all().order_by("pk")
        ids = list(types.values_list("id", flat=True))
        mergeform = PersonDocumentRelationTypeMergeForm(ids=ids[:-1])
        # total should have all but one type
        assert (
            mergeform.fields["primary_relation_type"].queryset.count()
            == types.count() - 1
        )
        # last type should not be an available choice
        assert types.last() not in mergeform.fields["primary_relation_type"].queryset


@pytest.mark.django_db
class TestPersonListForm:
    def test_set_choices_from_facets(self, person, person_diacritic):
        form = PersonListForm()
        with patch.object(FacetChoiceField, "populate_from_facets"):
            facets = {
                "gender": {"Male": 1, "Female": 2},
            }
            # should set labels and counts
            form.set_choices_from_facets(facets)
            form.fields["gender"].populate_from_facets.assert_called_with(
                {
                    "Female": ("Female", 2),
                    "Male": ("Male", 1),
                }
            )
            # should get translated labels
            facets = {
                "role": {person.role.name_en: 1},
            }
            form.set_choices_from_facets(facets)
            form.fields["social_role"].populate_from_facets.assert_called_with(
                {person.role.name_en: (person.role, 1)}
            )

    def test_get_translated_label(self):
        form = PersonListForm()
        # invalidate cached property (it is computed in other tests in the suite)
        if "objects_by_label" in PersonRole.__dict__:
            # __dict__["objects_by_label"] returns a classmethod
            # __func__ returns a property
            # fget returns the actual cached function
            PersonRole.__dict__["objects_by_label"].__func__.fget.cache_clear()

        # set lang to hebrew
        current_lang = get_language()
        activate("he")
        # PersonRole should be able to find the translated label
        pr = PersonRole.objects.create(
            name_en="Author", display_label_en="Author", display_label_he="מְחַבֵּר"
        )
        assert str(pr) == "מְחַבֵּר"
        assert str(form.get_translated_label("role", "Author")) == "מְחַבֵּר"
        # Gender should be able to find the translated label
        with patch("geniza.entities.models.Person") as mock_person:
            mock_person.GENDER_CHOICES = {"M": "test"}
            form.get_translated_label("gender", "Male") == "test"
        # Any other field not present in db mapping should return label as-is
        assert form.get_translated_label("no_field", "Test") == "Test"

        # set lang back for remaining tests
        activate(current_lang)

    def test_filters_active(self):
        # should correctly ascertain if filters are active
        form = PersonListForm({"gender": None})
        assert form.filters_active() == False
        form = PersonListForm({"gender": [Person.FEMALE]})
        assert form.filters_active() == True
        # sort SHOULD count as a filter (required for accurate facet counts after sorting)
        form = PersonListForm({"sort": "role"})
        assert form.filters_active() == True

    def test_get_sort_label(self):
        form = PersonListForm({})
        assert form.get_sort_label() is None

        form = PersonListForm({"sort": "role"})
        assert form.get_sort_label() == dict(PersonListForm.SORT_CHOICES)["role"]


@pytest.mark.django_db
class TestPlaceListForm:
    def test_get_sort_label(self):
        form = PlaceListForm({})
        assert form.get_sort_label() is None

        form = PlaceListForm({"sort": "name"})
        assert form.get_sort_label() == dict(PlaceListForm.SORT_CHOICES)["name"]
