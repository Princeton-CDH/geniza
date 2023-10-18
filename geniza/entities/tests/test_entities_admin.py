from unittest.mock import Mock

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from geniza.corpus.models import Document, LanguageScript
from geniza.entities.admin import (
    NameInlineFormSet,
    PersonAdmin,
    PersonDocumentInline,
    PersonPersonInline,
    PersonPersonRelationTypeChoiceField,
    PersonPersonReverseInline,
    PersonPlaceInline,
)
from geniza.entities.models import (
    Name,
    Person,
    PersonDocumentRelation,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    Place,
)


@pytest.mark.django_db
class TestPersonDocumentInline:
    def test_document_description(self):
        goitein = Person.objects.create()
        test_description = "A medieval poem"
        doc = Document.objects.create(description_en=test_description)
        relation = PersonDocumentRelation.objects.create(person=goitein, document=doc)
        inline = PersonDocumentInline(goitein, admin_site=admin.site)

        assert test_description == inline.document_description(relation)


@pytest.mark.django_db
class TestPersonPersonInline:
    def test_get_formset(self):
        # should set "type" field to PersonPersonRelationTypeChoiceField
        inline = PersonPersonInline(Person, admin_site=admin.site)
        formset = inline.get_formset(request=Mock())
        assert isinstance(
            formset.form.base_fields["type"], PersonPersonRelationTypeChoiceField
        )


@pytest.mark.django_db
class TestPersonPersonReverseInline:
    def test_relation(self):
        # should show converse relationship type when available
        (parent, _) = PersonPersonRelationType.objects.get_or_create(
            name="Parent",
            converse_name="Child",
            category=PersonPersonRelationType.IMMEDIATE_FAMILY,
        )
        ayala_gordon = Person.objects.create()
        sd_goitein = Person.objects.create()
        goitein_ayala = PersonPersonRelation.objects.create(
            from_person=ayala_gordon,
            to_person=sd_goitein,
            type=parent,
        )
        reverse_inline = PersonPersonReverseInline(Person, admin_site=admin.site)
        assert reverse_inline.relation(goitein_ayala) == "Child"

        # otherwise should just show relationship type
        (sibilng, _) = PersonPersonRelationType.objects.get_or_create(
            name="Sibling",
            category=PersonPersonRelationType.IMMEDIATE_FAMILY,
        )
        elon_goitein = Person.objects.create()
        goitein_siblings = PersonPersonRelation.objects.create(
            from_person=ayala_gordon,
            to_person=elon_goitein,
            type=sibilng,
        )
        assert reverse_inline.relation(goitein_siblings) == "Sibling"


@pytest.mark.django_db
class TestPersonPlaceInline:
    def test_place_link(self):
        goitein = Person.objects.create()
        place = Place.objects.create()
        relation = PersonPlaceRelation.objects.create(person=goitein, place=place)
        inline = PersonPlaceInline(Person, admin_site=admin.site)
        # should link to Place object
        place_link = inline.place_link(relation)
        assert str(place.id) in place_link
        assert str(place) in place_link


@pytest.mark.django_db
class TestPersonAdmin:
    def test_get_form(self):
        # should set own_pk property if obj exists
        goitein = Person.objects.create()
        person_admin = PersonAdmin(model=Person, admin_site=admin.site)
        mockrequest = Mock()
        person_admin.get_form(mockrequest, obj=goitein)
        assert person_admin.own_pk == goitein.pk

        # create new person, should be reset to None
        person_admin.get_form(mockrequest, obj=None)
        assert person_admin.own_pk == None

    def test_get_queryset(self):
        goitein = Person.objects.create()
        Person.objects.create()
        Person.objects.create()

        person_admin = PersonAdmin(model=Person, admin_site=admin.site)

        request_factory = RequestFactory()

        # simulate request for person list page
        request = request_factory.get("/admin/entities/person/")
        qs = person_admin.get_queryset(request)
        assert qs.count() == 3

        # simulate get_form setting own_pk
        person_admin.own_pk = goitein.pk

        # simulate person-person autocomplete request
        request = request_factory.get(
            "/admin/autocomplete/",
            {
                "app_label": "entities",
                "model_name": "personpersonrelation",
                "field_name": "to_person",
            },
        )
        qs = person_admin.get_queryset(request)
        # should exclude Person with pk=own_pk
        assert qs.count() == 2
        assert not qs.filter(pk=goitein.pk).exists()

        # simulate person-document autocomplete request
        request = request_factory.get(
            "/admin/autocomplete/",
            {
                "app_label": "entities",
                "model_name": "persondocumentrelation",
                "field_name": "person",
            },
        )
        qs = person_admin.get_queryset(request)
        assert qs.count() == 3


@pytest.mark.django_db
class TestNameInlineFormSet:
    def test_clean(self, admin_client):
        english = LanguageScript.objects.create(language="English", script="Latin")
        # should raise validation error if zero primary names
        response = admin_client.post(
            reverse("admin:entities_person_add"),
            data={
                "entities-name-content_type-object_id-INITIAL_FORMS": ["0"],
                "entities-name-content_type-object_id-TOTAL_FORMS": ["2"],
                "entities-name-content_type-object_id-MAX_NUM_FORMS": ["1000"],
                "entities-name-content_type-object_id-0-name": "Marina Rustow",
                "entities-name-content_type-object_id-0-language": str(english.pk),
                "entities-name-content_type-object_id-0-transliteration_style": Name.NONE,
                "entities-name-content_type-object_id-1-name": "S.D. Goitein",
                "entities-name-content_type-object_id-1-language": str(english.pk),
                "entities-name-content_type-object_id-1-transliteration_style": Name.NONE,
            },
        )
        assertContains(response, NameInlineFormSet.DISPLAY_NAME_ERROR)

        # should raise validation error if two primary names
        response = admin_client.post(
            reverse("admin:entities_person_add"),
            data={
                "entities-name-content_type-object_id-INITIAL_FORMS": ["0"],
                "entities-name-content_type-object_id-TOTAL_FORMS": ["2"],
                "entities-name-content_type-object_id-MAX_NUM_FORMS": ["1000"],
                "entities-name-content_type-object_id-0-name": "Marina Rustow",
                "entities-name-content_type-object_id-0-primary": "on",
                "entities-name-content_type-object_id-0-language": str(english.pk),
                "entities-name-content_type-object_id-0-transliteration_style": Name.NONE,
                "entities-name-content_type-object_id-1-name": "S.D. Goitein",
                "entities-name-content_type-object_id-1-primary": "on",
                "entities-name-content_type-object_id-1-language": str(english.pk),
                "entities-name-content_type-object_id-1-transliteration_style": Name.NONE,
            },
        )
        assertContains(response, NameInlineFormSet.DISPLAY_NAME_ERROR)

        # should NOT raise validation error if exactly one primary name
        response = admin_client.post(
            reverse("admin:entities_person_add"),
            data={
                "entities-name-content_type-object_id-INITIAL_FORMS": ["0"],
                "entities-name-content_type-object_id-TOTAL_FORMS": ["2"],
                "entities-name-content_type-object_id-MAX_NUM_FORMS": ["1000"],
                "entities-name-content_type-object_id-0-name": "Marina Rustow",
                "entities-name-content_type-object_id-0-primary": "on",
                "entities-name-content_type-object_id-0-language": str(english.pk),
                "entities-name-content_type-object_id-0-transliteration_style": Name.NONE,
                "entities-name-content_type-object_id-1-name": "S.D. Goitein",
                "entities-name-content_type-object_id-1-language": str(english.pk),
                "entities-name-content_type-object_id-1-transliteration_style": Name.NONE,
            },
        )
        assertNotContains(response, NameInlineFormSet.DISPLAY_NAME_ERROR)


@pytest.mark.django_db
class TestPersonPersonRelationTypeChoiceIterator:
    def test_iter(self):
        # create three types, one in one category and two in another
        type_a = PersonPersonRelationType.objects.create(
            category=PersonPersonRelationType.IMMEDIATE_FAMILY,
            name="Some family member",
        )
        type_b = PersonPersonRelationType.objects.create(
            category=PersonPersonRelationType.EXTENDED_FAMILY,
            name="Distant cousin",
        )
        type_c = PersonPersonRelationType.objects.create(
            category=PersonPersonRelationType.EXTENDED_FAMILY,
            name="Same category",
        )
        field = PersonPersonRelationTypeChoiceField(
            queryset=PersonPersonRelationType.objects.filter(
                pk__in=[type_a.pk, type_b.pk, type_c.pk],
            )
        )
        # field choice categories should use the full names, so grab those from model
        immediate_family = dict(PersonPersonRelationType.CATEGORY_CHOICES)[
            PersonPersonRelationType.IMMEDIATE_FAMILY
        ]
        extended_family = dict(PersonPersonRelationType.CATEGORY_CHOICES)[
            PersonPersonRelationType.EXTENDED_FAMILY
        ]
        # convert tuple to dict to make this easier to traverse
        choices = dict(field.choices)
        # choices should be grouped into their correct categories, as lists
        assert len(choices[immediate_family]) == 1
        assert len(choices[extended_family]) == 2
        assert (type_a.pk, type_a.name) in choices[immediate_family]
        assert (type_a.pk, type_a.name) not in choices[extended_family]
