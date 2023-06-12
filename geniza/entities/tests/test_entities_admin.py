import pytest
from django.contrib import admin
from django.test import RequestFactory

from geniza.entities.admin import PersonAdmin
from geniza.entities.models import Person


@pytest.mark.django_db
class TestPersonAdmin:
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
