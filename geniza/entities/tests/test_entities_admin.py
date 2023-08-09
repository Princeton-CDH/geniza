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
    PersonPlaceInline,
)
from geniza.entities.models import (
    Name,
    Person,
    PersonDocumentRelation,
    PersonPersonRelation,
    PersonPlaceRelation,
    Place,
)


@pytest.mark.django_db
class TestPersonDocumentInline:
    def test_document_link(self):
        goitein = Person.objects.create()
        doc = Document.objects.create()
        relation = PersonDocumentRelation.objects.create(person=goitein, document=doc)
        inline = PersonDocumentInline(goitein, admin_site=admin.site)

        doc_link = inline.document_link(relation)

        assert str(doc.id) in doc_link
        assert str(doc) in doc_link

    def test_document_description(self):
        goitein = Person.objects.create()
        test_description = "A medieval poem"
        doc = Document.objects.create(description_en=test_description)
        relation = PersonDocumentRelation.objects.create(person=goitein, document=doc)
        inline = PersonDocumentInline(goitein, admin_site=admin.site)

        assert test_description == inline.document_description(relation)


@pytest.mark.django_db
class TestPersonPersonInline:
    def test_person_link(self):
        goitein = Person.objects.create()
        rustow = Person.objects.create()
        relation = PersonPersonRelation.objects.create(
            from_person=goitein, to_person=rustow
        )
        inline = PersonPersonInline(Person, admin_site=admin.site)
        # should link to to_person Person object
        person_link = inline.person_link(relation)
        assert str(rustow.id) in person_link
        assert str(rustow) in person_link


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

    def test_get_queryset(self):
        goitein = Person.objects.create()
        Person.objects.create()
        Person.objects.create()

        person_admin = PersonAdmin(model=Person, admin_site=admin.site)

        request_factory = RequestFactory()

        # simulate request for person list page
        request = request_factory.post("/admin/entities/person/")
        qs = person_admin.get_queryset(request)
        assert qs.count() == 3

        # simulate get_form setting own_pk
        person_admin.own_pk = goitein.pk

        # simulate autocomplete request
        request = request_factory.post("/admin/autocomplete/")
        qs = person_admin.get_queryset(request)
        # should exclude Person with pk=own_pk
        assert qs.count() == 2
        assert not qs.filter(pk=goitein.pk).exists()


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
