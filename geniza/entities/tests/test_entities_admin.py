from unittest.mock import Mock

import pytest
from django.contrib import admin
from django.test import RequestFactory

from geniza.corpus.models import Document
from geniza.entities.admin import (
    PersonAdmin,
    PersonDocumentInline,
    PersonPersonInline,
    PersonPersonRelationTypeChoiceField,
)
from geniza.entities.models import (
    Person,
    PersonDocumentRelation,
    PersonPersonRelation,
    PersonPersonRelationType,
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

    def test_get_formset(self):
        # should set "type" field to PersonPersonRelationTypeChoiceField
        inline = PersonPersonInline(Person, admin_site=admin.site)
        formset = inline.get_formset(request=Mock())
        assert isinstance(
            formset.form.base_fields["type"], PersonPersonRelationTypeChoiceField
        )


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
