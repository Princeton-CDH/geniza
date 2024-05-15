from unittest.mock import Mock, patch

import pytest
from django.forms import ValidationError
from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils.text import Truncator

from geniza.corpus.models import Document
from geniza.entities.forms import PersonListForm
from geniza.entities.models import (
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonRole,
    Place,
)
from geniza.entities.views import (
    PersonAutocompleteView,
    PersonDetailView,
    PersonListView,
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
        for _ in range(Person.MIN_DOCUMENTS):
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
class TestPersonListView:
    def test_get_queryset__order(self, person, person_diacritic, person_multiname):
        personlist_view = PersonListView()
        with patch.object(personlist_view, "get_form") as mock_get_form:
            mock_get_form.return_value.cleaned_data = {}
            mock_get_form.return_value.is_valid.return_value = True
            # should order diacritics unaccented
            qs = personlist_view.get_queryset()
            assert qs.first().pk == person.pk  # Berakha
            assert qs[1].pk == person_diacritic.pk  # Halfon
            # should order by primary name only
            assert qs[2].pk == person_multiname.pk  # Zed

    def test_get_queryset__invalidform(self):
        # should give empty queryset on invalid form
        personlist_view = PersonListView()
        with patch.object(personlist_view, "get_form") as mock_get_form:
            mock_get_form.return_value.cleaned_data = {}
            mock_get_form.return_value.is_valid.return_value = False
            qs = personlist_view.get_queryset()
            assert qs.count() == 0

    def test_get_queryset__filters(
        self, document, join, person, person_diacritic, person_multiname
    ):
        # add document relations
        (mentioned, _) = PersonDocumentRelationType.objects.get_or_create(
            name_en="Other person mentioned"
        )
        (author, _) = PersonDocumentRelationType.objects.get_or_create(name_en="Author")
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=mentioned
        )
        PersonDocumentRelation.objects.create(
            person=person_diacritic, document=document, type=mentioned
        )
        PersonDocumentRelation.objects.create(
            person=person_diacritic, document=join, type=author
        )
        PersonDocumentRelation.objects.create(
            person=person_multiname, document=join, type=author
        )

        personlist_view = PersonListView()
        with patch.object(personlist_view, "get_form") as mock_get_form:
            # filter by gender: F should return 2 records
            # form data comes in as string that we use literal_eval to parse
            mock_get_form.return_value.cleaned_data = {"gender": f"['{Person.FEMALE}']"}
            mock_get_form.return_value.is_valid.return_value = True
            qs = personlist_view.get_queryset()
            assert qs.count() == 2
            assert person in qs
            assert person_diacritic not in qs

            # [M, F] should return all 3
            mock_get_form.return_value.cleaned_data = {
                "gender": f"['{Person.FEMALE}', '{Person.MALE}']"
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 3
            # should be sorted by primary name
            assert qs.first() == person
            assert qs.last() == person_multiname

            # filter by social role
            mock_get_form.return_value.cleaned_data = {
                "social_role": f"['{person.role.name}']"
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 2

            # filter by social role and gender
            mock_get_form.return_value.cleaned_data = {
                "social_role": f"['{person.role.name}']",
                "gender": f"['{Person.FEMALE}']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 1

            # filter by doc relation
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{mentioned.name_en}']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 2
            assert person_diacritic in qs
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{author.name_en}']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 2
            assert person_diacritic in qs
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{author.name_en}']",
                "gender": f"['{Person.MALE}']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 1

            # ---- sort ----
            # sort by related documents: ascending
            mock_get_form.return_value.cleaned_data = {"sort": "documents"}
            qs = personlist_view.get_queryset()
            assert qs.first().pk != person_diacritic.pk

            # sort by related documents: descending
            mock_get_form.return_value.cleaned_data = {
                "sort": "documents",
                "sort_dir": "desc",
            }
            qs = personlist_view.get_queryset()
            assert qs.first().pk == person_diacritic.pk

    def test_get_facets(
        self, document, join, person, person_diacritic, person_multiname
    ):
        # add document relations
        (mentioned, _) = PersonDocumentRelationType.objects.get_or_create(
            name_en="Other person mentioned"
        )
        (author, _) = PersonDocumentRelationType.objects.get_or_create(name_en="Author")
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=mentioned
        )
        PersonDocumentRelation.objects.create(
            person=person_diacritic, document=document, type=mentioned
        )
        PersonDocumentRelation.objects.create(
            person=person_multiname, document=join, type=author
        )
        personlist_view = PersonListView()
        with patch.object(personlist_view, "get_form") as mock_get_form:
            mock_get_form.return_value.is_valid.return_value = True

            # unfiltered results should get all facets annotated with counts
            mock_get_form.return_value.is_filtered.return_value = False
            mock_get_form.return_value.cleaned_data = {}
            facets = personlist_view.get_facets()
            assert all(
                any([d["role__name"] == role for d in facets["role__name"]])
                for role in [
                    person.role.name,
                    person_diacritic.role.name,
                    person_multiname.role.name,
                ]
            )
            get_count = lambda field, val: [
                item for item in facets[field] if item[field] == val
            ][0]["count"]
            # person and person_diacritic share a role, so count should be 2
            assert get_count("role__name", person.role.name) == 2
            # person_multiname is the only one with their role
            assert get_count("role__name", person_multiname.role.name) == 1
            # two entries with female gender
            assert get_count("gender", Person.FEMALE) == 2
            # two entries with document relation = mentioned
            assert (
                get_count("persondocumentrelation__type__name", mentioned.name_en) == 2
            )

            # mock filters applied
            mock_get_form.return_value.is_filtered.return_value = True
            mock_get_form.return_value.cleaned_data = {
                "social_role": f"['{person.role.name}']"
            }
            facets = personlist_view.get_facets()

            # should accurately update the facet counts
            assert get_count("role__name", person.role.name) == 2
            assert get_count("gender", Person.FEMALE) == 1

            # should include 0 counts for values present in db but filtered out
            assert get_count("role__name", person_multiname.role.name) == 0
            assert get_count("persondocumentrelation__type__name", author.name_en) == 0

    def test_get_context_data(self, client, person):
        with patch.object(PersonListForm, "set_choices_from_facets") as mock_setchoices:
            response = client.get(reverse("entities:person-list"))
            # context should include "page_type": "people"
            assert response.context["page_type"] == "people"
            # should get facets with counts
            assert isinstance(response.context["facets"], dict)
            # should call set_choices_from_facets on form
            mock_setchoices.assert_called_once()

    def test_get_form_kwargs(self, client):
        # should use initial values if not set
        response = client.get(reverse("entities:person-list"))
        assert (
            response.context["form"].cleaned_data["sort"]
            == PersonListView.initial["sort"]
        )
        # should not overwrite values from request if they are set
        sort_role = "role"
        response = client.get(reverse("entities:person-list"), {"sort": sort_role})
        assert response.context["form"].cleaned_data["sort"] == sort_role


@pytest.mark.django_db
class TestSlugDetailMixin:
    def test_get(self, client):
        # should redirect on past slug
        person = Person.objects.create(has_page=True)
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


@pytest.mark.django_db
class TestPlaceDetailView:
    def test_page_title(self, client):
        # should use primary name as page title
        place = Place.objects.create()
        name1 = Name.objects.create(name="Fustat", content_object=place, primary=True)
        Name.objects.create(name="Secondary Name", content_object=place, primary=False)
        place.generate_slug()
        place.save()
        response = client.get(reverse("entities:place", args=(place.slug,)))
        assert response.context["page_title"] == str(name1)

    def test_page_description(self, client):
        # should use place notes as page description
        place = Place.objects.create(notes="Example", slug="test")
        response = client.get(reverse("entities:place", args=(place.slug,)))
        assert response.context["page_description"] == "Example"

        # should truncate long notes
        long_notes = " ".join(["test" for _ in range(50)])
        place.notes = long_notes
        place.save()
        response = client.get(reverse("entities:place", args=(place.slug,)))
        assert response.context["page_description"] == Truncator(long_notes).words(20)

    @override_settings(MAPTILER_API_TOKEN="example")
    def test_get_context_data(self, client):
        place = Place.objects.create(slug="test")
        response = client.get(reverse("entities:place", args=(place.slug,)))
        # context should include "page_type": "place"
        assert response.context["page_type"] == "place"
        # context should include the maptiler token if one exists in settings
        assert response.context["maptiler_token"] == "example"
