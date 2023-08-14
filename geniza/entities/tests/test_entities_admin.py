from unittest.mock import Mock

import pytest
from django.contrib import admin
from django.test import RequestFactory

from geniza.corpus.models import Document
from geniza.entities.admin import PersonAdmin, PersonDocumentInline, PersonPersonInline
from geniza.entities.models import Person, PersonDocumentRelation, PersonPersonRelation


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
