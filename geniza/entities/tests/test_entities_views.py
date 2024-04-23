from unittest.mock import Mock, patch

import pytest
from django.forms import ValidationError
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils.text import Truncator

from geniza.corpus.models import Document
from geniza.entities.models import Name, Person, Place
from geniza.entities.views import (
    PersonAutocompleteView,
    PersonDetailView,
    PersonMerge,
    PlaceAutocompleteView,
)


class TestPersonMergeView:
    # adapted from TestDocumentMergeView
    @pytest.mark.django_db
    def test_get_success_url(self):
        person = Person.objects.create()
        merge_view = PersonMerge()
        merge_view.primary_person = person

        resolved_url = resolve(merge_view.get_success_url())
        assert "admin" in resolved_url.app_names
        assert resolved_url.url_name == "entities_person_change"
        assert resolved_url.kwargs["object_id"] == str(person.pk)

    def test_get_initial(self):
        merge_view = PersonMerge()
        merge_view.request = Mock(GET={"ids": "12,23,456,7"})

        initial = merge_view.get_initial()
        assert merge_view.person_ids == [12, 23, 456, 7]
        # lowest id selected as default primary person
        assert initial["primary_person"] == 7

        # Test when no ids are provided (a user shouldn't get here,
        #  but shouldn't raise an error.)
        merge_view.request = Mock(GET={"ids": ""})
        initial = merge_view.get_initial()
        assert merge_view.person_ids == []
        merge_view.request = Mock(GET={})
        initial = merge_view.get_initial()
        assert merge_view.person_ids == []

    def test_get_form_kwargs(self):
        merge_view = PersonMerge()
        merge_view.request = Mock(GET={"ids": "12,23,456,7"})
        form_kwargs = merge_view.get_form_kwargs()
        assert form_kwargs["person_ids"] == merge_view.person_ids

    def test_person_merge(self, admin_client, client):
        # Ensure that the person merge view is not visible to public
        response = client.get(reverse("admin:person-merge"))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

        # create test person records to merge
        person = Person.objects.create()
        dupe_person = Person.objects.create()

        person_ids = [person.id, dupe_person.id]
        idstring = ",".join(str(pid) for pid in person_ids)

        # GET should display choices
        response = admin_client.get(reverse("admin:person-merge"), {"ids": idstring})
        assert response.status_code == 200

        # POST should merge
        merge_url = "%s?ids=%s" % (reverse("admin:person-merge"), idstring)
        response = admin_client.post(
            merge_url, {"primary_person": person.id}, follow=True
        )
        TestCase().assertRedirects(
            response, reverse("admin:entities_person_change", args=[person.id])
        )
        message = list(response.context.get("messages"))[0]
        assert message.tags == "success"
        assert "Successfully merged" in message.message
        assert f"with {str(person)} (id = {person.pk})" in message.message

        with patch.object(Person, "merge_with") as mock_merge_with:
            # should catch ValidationError and send back to form with error msg
            mock_merge_with.side_effect = ValidationError("test message")
            response = admin_client.post(
                merge_url, {"primary_person": person.id}, follow=True
            )
            TestCase().assertRedirects(response, merge_url)
            messages = [str(msg) for msg in list(response.context["messages"])]
            assert "test message" in messages


class TestPersonAutocompleteView:
    @pytest.mark.django_db
    def test_get_queryset(self):
        # create two people
        person = Person.objects.create()
        Name.objects.create(
            name="Mūsā b. Yaḥyā al-Majjānī", content_object=person, primary=True
        )
        Name.objects.create(name="Abū 'Imrān", content_object=person, primary=False)
        person_2 = Person.objects.create()
        Name.objects.create(
            name="Ḥayyim b. 'Ammār al-Madīnī", content_object=person_2, primary=True
        )
        person_autocomplete_view = PersonAutocompleteView()
        # mock request with empty search
        person_autocomplete_view.request = Mock()
        person_autocomplete_view.request.GET = {"q": ""}
        qs = person_autocomplete_view.get_queryset()
        # should get exactly two results (all people) even though one has two names
        assert qs.count() == 2

        # should filter on names, case and diacritic insensitive
        person_autocomplete_view.request.GET = {"q": "musa b. yahya"}
        qs = person_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == person.pk

        # should allow search by non-primary name
        person_autocomplete_view.request.GET = {"q": "imran"}
        qs = person_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == person.pk

        # should allow search by name WITH diacritics
        person_autocomplete_view.request.GET = {"q": "Ḥayyim"}
        qs = person_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == person_2.pk


class TestPlaceAutocompleteView:
    @pytest.mark.django_db
    def test_get_queryset(self):
        # create a place
        place = Place.objects.create()
        Name.objects.create(name="Fusṭāṭ", content_object=place, primary=True)
        place_autocomplete_view = PlaceAutocompleteView()

        # should filter on place name, case and diacritic insensitive
        place_autocomplete_view.request = Mock()
        place_autocomplete_view.request.GET = {"q": "Fusṭāṭ"}
        qs = place_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == place.pk

        place_autocomplete_view.request.GET = {"q": "fustat"}
        qs = place_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == place.pk


@pytest.mark.django_db
class TestPersonDetailView:
    def test_page_title(self, client):
        # should use primary name as page title
        person = Person.objects.create(has_page=True)
        name1 = Name.objects.create(
            name="Mūsā b. Yaḥyā al-Majjānī", content_object=person, primary=True
        )
        Name.objects.create(name="Abū 'Imrān", content_object=person, primary=False)
        person.generate_slug()
        person.save()
        response = client.get(reverse("entities:person", args=(person.slug,)))
        assert response.context["page_title"] == str(name1)

    def test_page_description(self, client):
        # should use person description as page description
        person = Person.objects.create(
            has_page=True, description_en="Example", slug="test"
        )
        response = client.get(reverse("entities:person", args=(person.slug,)))
        assert response.context["page_description"] == "Example"

        # should truncate long description
        long_description = " ".join(["test" for _ in range(50)])
        person.description = long_description
        person.save()
        response = client.get(reverse("entities:person", args=(person.slug,)))
        assert response.context["page_description"] == Truncator(
            long_description
        ).words(20)

    def test_get_queryset(self, client):
        # should 404 on person with has_page=False and < 10 related documents
        person = Person.objects.create(slug="test")
        response = client.get(reverse("entities:person", args=(person.slug,)))
        assert response.status_code == 404

        # should 200 on person with 10+ associated documents
        for _ in range(PersonDetailView.MIN_DOCUMENTS):
            d = Document.objects.create()
            person.documents.add(d)
        response = client.get(reverse("entities:person", args=(person.slug,)))
        assert response.status_code == 200

        # should 200 on person with has_page = True
        person_override = Person.objects.create(has_page=True, slug="has-page")
        response = client.get(reverse("entities:person", args=(person_override.slug,)))
        assert response.status_code == 200

    def test_get_context_data(self, client):
        # context should include "page_type": "person"
        person = Person.objects.create(has_page=True, slug="test")
        response = client.get(reverse("entities:person", args=(person.slug,)))
        assert response.context["page_type"] == "person"


@pytest.mark.django_db
class TestPersonDetailMixin:
    def test_get(self, client):
        # should redirect on past slug
        person = Person.objects.create()
        name1 = Name.objects.create(name="Imran", content_object=person, primary=True)
        person.generate_slug()
        person.save()
        old_slug = person.slug

        name1.primary = False
        name1.save()
        Name.objects.create(name="Abū 'Imrān", content_object=person, primary=True)
        person.generate_slug()
        person.save()

        response = client.get(reverse("entities:person", args=(old_slug,)))
        assert response.status_code == 301
        assert response.url == person.get_absolute_url()

        # should still raise 404 if conditions aren't met (has_page or MIN_DOCUMENTS)
        assert client.get(response.url).status_code == 404
