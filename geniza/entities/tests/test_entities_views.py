import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.forms import ValidationError
from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils.text import Truncator
from parasolr.django import SolrClient

from geniza.corpus.dates import Calendar
from geniza.corpus.models import Dating, Document, DocumentType, TextBlock
from geniza.entities.forms import PersonListForm
from geniza.entities.models import (
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    PersonSolrQuerySet,
    Place,
    PlacePlaceRelation,
    PlacePlaceRelationType,
    PlaceSolrQuerySet,
)
from geniza.entities.views import (
    PersonAutocompleteView,
    PersonDocumentRelationTypeMerge,
    PersonListView,
    PersonMerge,
    PersonPersonRelationTypeMerge,
    PlaceAutocompleteView,
    PlaceListSnippetView,
    PlaceListView,
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


class TestPersonDocumentRelationTypeMergeView:
    # adapted from TestPersonMergeView
    @pytest.mark.django_db
    def test_get_success_url(self):
        rel_type = PersonDocumentRelationType.objects.create(name="test")
        merge_view = PersonDocumentRelationTypeMerge()
        merge_view.primary_relation_type = rel_type

        resolved_url = resolve(merge_view.get_success_url())
        assert "admin" in resolved_url.app_names
        assert resolved_url.url_name == "entities_persondocumentrelationtype_change"
        assert resolved_url.kwargs["object_id"] == str(rel_type.pk)

    def test_get_initial(self):
        merge_view = PersonDocumentRelationTypeMerge()
        merge_view.request = Mock(GET={"ids": "12,23,456,7"})

        initial = merge_view.get_initial()
        assert merge_view.ids == [12, 23, 456, 7]
        # lowest id selected as default primary type
        assert initial["primary_relation_type"] == 7

        # Test when no ids are provided (a user shouldn't get here,
        #  but shouldn't raise an error.)
        merge_view.request = Mock(GET={"ids": ""})
        initial = merge_view.get_initial()
        assert merge_view.ids == []
        merge_view.request = Mock(GET={})
        initial = merge_view.get_initial()
        assert merge_view.ids == []

    def test_get_form_kwargs(self):
        merge_view = PersonDocumentRelationTypeMerge()
        merge_view.request = Mock(GET={"ids": "12,23,456,7"})
        form_kwargs = merge_view.get_form_kwargs()
        assert form_kwargs["ids"] == merge_view.ids

    def test_person_document_relation_type_merge(self, admin_client, client):
        # Ensure that the merge view is not visible to public
        response = client.get(reverse("admin:person-document-relation-type-merge"))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

        # create test records to merge
        rel_type = PersonDocumentRelationType.objects.create(name="test")
        dupe_rel_type = PersonDocumentRelationType.objects.create(name="test2")

        idstring = ",".join(str(id) for id in [rel_type.id, dupe_rel_type.id])

        # GET should display choices
        response = admin_client.get(
            reverse("admin:person-document-relation-type-merge"), {"ids": idstring}
        )
        assert response.status_code == 200

        # POST should merge
        merge_url = "%s?ids=%s" % (
            reverse("admin:person-document-relation-type-merge"),
            idstring,
        )
        response = admin_client.post(
            merge_url, {"primary_relation_type": rel_type.id}, follow=True
        )
        TestCase().assertRedirects(
            response,
            reverse(
                "admin:entities_persondocumentrelationtype_change", args=[rel_type.id]
            ),
        )
        message = list(response.context.get("messages"))[0]
        assert message.tags == "success"
        assert "Successfully merged" in message.message
        assert f"with {str(rel_type)} (id = {rel_type.pk})" in message.message

        with patch.object(PersonDocumentRelationType, "merge_with") as mock_merge_with:
            # should catch ValidationError and send back to form with error msg
            mock_merge_with.side_effect = ValidationError("test message")
            response = admin_client.post(
                merge_url, {"primary_relation_type": rel_type.id}, follow=True
            )
            TestCase().assertRedirects(response, merge_url)
            messages = [str(msg) for msg in list(response.context["messages"])]
            assert "test message" in messages


class TestPersonPersonRelationTypeMergeView:
    # adapted from TestPersonMergeView
    @pytest.mark.django_db
    def test_get_success_url(self):
        rel_type = PersonPersonRelationType.objects.create(name="test")
        merge_view = PersonPersonRelationTypeMerge()
        merge_view.primary_relation_type = rel_type

        resolved_url = resolve(merge_view.get_success_url())
        assert "admin" in resolved_url.app_names
        assert resolved_url.url_name == "entities_personpersonrelationtype_change"
        assert resolved_url.kwargs["object_id"] == str(rel_type.pk)


@pytest.mark.django_db
class TestPersonAutocompleteView:
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
        person_autocomplete_view.request.META = {}
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

    def test_get_queryset__personperson_form(self, person, person_multiname):
        person_autocomplete_view = PersonAutocompleteView()
        # mock request
        person_autocomplete_view.request = Mock()
        person_autocomplete_view.request.META = {}
        person_autocomplete_view.request.GET = {"q": ""}
        qs = person_autocomplete_view.get_queryset()
        # should get exactly two results (all people)
        assert qs.count() == 2

        # simulate person-person autocomplete: mock META and forwarded
        change_url = reverse("admin:entities_person_change", args=[person.id])
        person_autocomplete_view.request.META = {"HTTP_REFERER": change_url}
        person_autocomplete_view.forwarded = {"is_person_person_form": True}
        qs = person_autocomplete_view.get_queryset()
        # should get one result, excluding the one whose id is in referrer
        assert qs.count() == 1


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
    def test_get_queryset__order(
        self, person, person_diacritic, person_multiname, empty_solr
    ):
        personlist_view = PersonListView()
        SolrClient().update.index(
            [
                person.index_data(),
                person_diacritic.index_data(),
                person_multiname.index_data(),
            ],
            commit=True,
        )
        Person.index_items([person, person_diacritic, person_multiname])
        with patch.object(personlist_view, "get_form") as mock_get_form:
            mock_get_form.return_value.cleaned_data = {}
            mock_get_form.return_value.is_valid.return_value = True
            # should order diacritics unaccented
            qs = personlist_view.get_queryset()
            assert qs[0].get("slug") == person.slug  # Berakha
            assert qs[1].get("slug") == person_diacritic.slug  # Halfon
            # should order by primary name only
            assert qs[2].get("slug") == person_multiname.slug  # Zed

    def test_get_queryset__invalidform(self):
        # should give empty queryset on invalid form
        personlist_view = PersonListView()
        with patch.object(personlist_view, "get_form") as mock_get_form:
            mock_get_form.return_value.cleaned_data = {}
            mock_get_form.return_value.is_valid.return_value = False
            qs = personlist_view.get_queryset()
            assert qs.count() == 0

    def test_get_queryset__filters(
        self, document, join, person, person_diacritic, person_multiname, empty_solr
    ):
        # add document relations
        (mentioned, _) = PersonDocumentRelationType.objects.get_or_create(
            name_en="Other person mentioned"
        )
        (author, _) = PersonDocumentRelationType.objects.get_or_create(name_en="Author")
        (scribe, _) = PersonDocumentRelationType.objects.get_or_create(name_en="Scribe")
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
        # certainty
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=scribe, uncertain=False
        )
        PersonDocumentRelation.objects.create(
            person=person_diacritic, document=join, type=scribe, uncertain=True
        )
        PersonDocumentRelation.objects.create(
            person=person_multiname, document=document, type=scribe, uncertain=True
        )
        person.date = "990/1020"
        person.has_page = True
        person.save()
        person_diacritic.date = "1150"
        person_diacritic.save()

        SolrClient().update.index(
            [
                person.index_data(),
                person_diacritic.index_data(),
                person_multiname.index_data(),
            ],
            commit=True,
        )
        personlist_view = PersonListView()
        with patch.object(personlist_view, "get_form") as mock_get_form:
            # filter by gender: F should return 2 records
            # form data comes in as string that we use literal_eval to parse
            mock_get_form.return_value.cleaned_data = {"gender": f"['Female']"}
            mock_get_form.return_value.is_valid.return_value = True
            qs = personlist_view.get_queryset()
            assert qs.count() == 2
            assert any(p.get("slug") == person.slug for p in qs)
            assert not any(p.get("slug") == person_diacritic.slug for p in qs)

            # [M, F] should return all 3
            mock_get_form.return_value.cleaned_data = {"gender": f"['Female', 'Male']"}
            qs = personlist_view.get_queryset()
            assert qs.count() == 3
            # should be sorted by primary name
            assert qs[0].get("slug") == person.slug
            assert qs[1].get("slug") == person_diacritic.slug
            assert qs[2].get("slug") == person_multiname.slug

            # filter by social role
            mock_get_form.return_value.cleaned_data = {
                "social_role": f"['{person.roles.first().name}']"
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 2

            # filter by social role and gender
            mock_get_form.return_value.cleaned_data = {
                "social_role": f"['{person.roles.first().name}']",
                "gender": f"['Female']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 1

            # filter by doc relation
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{mentioned.name_en}']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 2
            assert any(p.get("slug") == person_diacritic.slug for p in qs)
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{author.name_en}']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 2
            assert any(p.get("slug") == person_diacritic.slug for p in qs)
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{author.name_en}']",
                "gender": f"['Male']",
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 1

            # filter by CERTAIN document relation
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{scribe.name_en}']",
                "exclude_uncertain": True,
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 1
            mock_get_form.return_value.cleaned_data = {
                "document_relation": f"['{scribe.name_en}']",
                "exclude_uncertain": False,
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 3

            # filter by detail page
            mock_get_form.return_value.cleaned_data = {"has_page": True}
            qs = personlist_view.get_queryset()
            assert qs.count() == 1
            assert any(
                (f["field"] == "has_page" and f["value"] == "on")
                for f in personlist_view.applied_filter_labels
            )

            # filter by dates
            mock_get_form.return_value.cleaned_data = {
                "date_range": ("1000", "1200"),
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 2
            assert any(
                f["label"] == "1000–1200" for f in personlist_view.applied_filter_labels
            )

            mock_get_form.return_value.cleaned_data = {
                "date_range": ("1100", None),
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 1
            assert qs[0].get("slug") == person_diacritic.slug
            assert any(
                f["label"] == "After 1100"
                for f in personlist_view.applied_filter_labels
            )

            mock_get_form.return_value.cleaned_data = {
                "date_range": (None, "1100"),
            }
            qs = personlist_view.get_queryset()
            assert qs.count() == 1
            assert qs[0].get("slug") == person.slug
            assert any(
                f["label"] == "Before 1100"
                for f in personlist_view.applied_filter_labels
            )

            # ---- sort ----
            # sort by related documents: ascending
            mock_get_form.return_value.cleaned_data = {"sort": "documents"}
            qs = personlist_view.get_queryset()
            assert qs[0].get("slug") != person_diacritic.slug

            # sort by related documents: descending
            mock_get_form.return_value.cleaned_data = {
                "sort": "documents",
                "sort_dir": "desc",
            }
            qs = personlist_view.get_queryset()
            assert qs[0].get("slug") == person_diacritic.slug

            # sort by date asc and desc (different fields)
            with patch.object(PersonSolrQuerySet, "order_by") as mock_order_by:
                mock_get_form.return_value.cleaned_data = {
                    "sort": "date",
                    "sort_dir": "desc",
                }
                personlist_view.get_queryset()
                mock_order_by.assert_called_with("-end_dating_i")
                mock_get_form.return_value.cleaned_data = {
                    "sort": "date",
                    "sort_dir": "asc",
                }
                personlist_view.get_queryset()
                mock_order_by.assert_called_with("start_dating_i")

    def test_get_queryset__keyword_query(
        self, person, person_diacritic, person_multiname, empty_solr
    ):
        SolrClient().update.index(
            [
                person.index_data(),
                person_diacritic.index_data(),
                person_multiname.index_data(),
            ],
            commit=True,
        )
        personlist_view = PersonListView()
        with patch.object(personlist_view, "get_form") as mock_get_form:
            mock_get_form.return_value.cleaned_data = {"q": str(person)}
            qs = personlist_view.get_queryset()
            # should return the person
            assert qs.count() == 1
            resulting_ids = [result["id"] for result in qs]
            assert f"person.{person.id}" in resulting_ids

            Name.objects.create(name=str(person), content_object=person_multiname)
            SolrClient().update.index([person_multiname.index_data()], commit=True)
            mock_get_form.return_value.cleaned_data = {
                "q": str(person),
                "sort": "relevance",
                "sort_dir": "desc",
            }
            qs = personlist_view.get_queryset()
            # should return both people
            assert qs.count() == 2
            resulting_ids = [result["id"] for result in qs]
            assert f"person.{person.id}" in resulting_ids
            assert f"person.{person_multiname.id}" in resulting_ids
            # primary name should be prioritized above other names in relevance
            assert qs[0]["id"] == f"person.{person.id}"
            assert qs[0]["score"] > qs[1]["score"]
            # other names should be highlighted
            highlights = qs.get_highlighting()
            assert f"person.{person_multiname.id}" in highlights
            assert "other_names" in highlights[f"person.{person_multiname.id}"]

    def test_get_context_data(self, client, person):
        with patch.object(PersonListForm, "set_choices_from_facets") as mock_setchoices:
            response = client.get(reverse("entities:person-list"))
            # context should include "page_type": "people"
            assert response.context["page_type"] == "people"
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
        sort_name = "name"
        response = client.get(reverse("entities:person-list"), {"sort": sort_name})
        assert response.context["form"].cleaned_data["sort"] == sort_name

    def test_get_applied_filter_labels(self):
        # should return list of dicts with field, value, translated label
        form = Mock()
        form.get_translated_label.side_effect = ["מְחַבֵּר", "סוֹפֵר"]
        doc_relation_filters = PersonListView.get_applied_filter_labels(
            None, form, "document_relation", ["Author", "Scribe"]
        )
        assert doc_relation_filters == [
            {"field": "document_relation", "value": "Author", "label": "מְחַבֵּר"},
            {"field": "document_relation", "value": "Scribe", "label": "סוֹפֵר"},
        ]

        # should remove escape characters
        form = Mock()
        form.get_translated_label.return_value = "פקיד המדינה"
        social_role_filters = PersonListView.get_applied_filter_labels(
            None, form, "social_role", ["State\ official"]
        )
        assert social_role_filters == [
            {"field": "social_role", "value": "State official", "label": "פקיד המדינה"}
        ]


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

    def test_related_places(self, client):
        tlebanon = Place.objects.create(slug="tripoli-lebanon")
        Name.objects.create(
            name="Tripoli (Lebanon)", content_object=tlebanon, primary=True
        )

        # create some place-place relationshipss
        tgreece = Place.objects.create(slug="tripoli-greece")
        Name.objects.create(
            name="Tripoli (Greece)", content_object=tgreece, primary=True
        )
        (nbc, _) = PlacePlaceRelationType.objects.get_or_create(
            name="Not to be confused with"
        )
        PlacePlaceRelation.objects.create(place_a=tlebanon, place_b=tgreece, type=nbc)

        # add an asymmetrical one from another place, it should show up too, but with converse name
        zahriyeh = Place.objects.create(slug="zahriyeh")
        Name.objects.create(name="Zahriyeh", content_object=zahriyeh, primary=True)
        (city_neighborhood, _) = PlacePlaceRelationType.objects.get_or_create(
            name="City", converse_name="Neighborhood"
        )
        PlacePlaceRelation.objects.create(
            place_a=zahriyeh, place_b=tlebanon, type=city_neighborhood
        )

        response = client.get(reverse("entities:place", args=(tlebanon.slug,)))
        assert len(response.context["related_places"]) == 2
        # should be ordered by type name
        assert (
            response.context["related_places"][0]["type"]
            == city_neighborhood.converse_name
        )
        assert response.context["related_places"][0]["use_converse_typename"] == True
        assert response.context["related_places"][0]["name"] == str(zahriyeh)
        assert response.context["related_places"][1]["type"] == nbc.name
        assert response.context["related_places"][1]["use_converse_typename"] == False
        assert response.context["related_places"][1]["name"] == str(tgreece)

        # create a duplicate of the asymmetric relation to test dedupe
        (subset_superset, _) = PlacePlaceRelationType.objects.get_or_create(
            name="Subset", converse_name="Superset"
        )
        PlacePlaceRelation.objects.create(
            place_a=tlebanon, place_b=zahriyeh, type=subset_superset
        )
        response = client.get(reverse("entities:place", args=(tlebanon.slug,)))
        assert len(response.context["related_places"]) == 2
        bothtypes = response.context["related_places"][0]["type"].lower()
        assert (
            city_neighborhood.converse_name.lower() in bothtypes
            and subset_superset.name.lower() in bothtypes
        )


@pytest.mark.django_db
class TestPersonDocumentsView:
    def test_page_title(self, client, document):
        # should use primary name in page title
        person = Person.objects.create(has_page=True)
        name1 = Name.objects.create(
            name="Mūsā b. Yaḥyā al-Majjānī", content_object=person, primary=True
        )
        Name.objects.create(name="Abū 'Imrān", content_object=person, primary=False)
        person.generate_slug()
        person.save()
        person.documents.add(document)
        response = client.get(reverse("entities:person-documents", args=(person.slug,)))
        assert response.context["page_title"] == f"Related documents for {str(name1)}"

    def test_page_description(self, client, document, join):
        # should correctly count the number of related documents
        person = Person.objects.create(has_page=True)
        Name.objects.create(name="Goitein", content_object=person, primary=True)
        person.generate_slug()
        person.save()
        person.documents.add(document)
        response = client.get(reverse("entities:person-documents", args=(person.slug,)))
        assert "1 related document" in response.context["page_description"]
        person.documents.add(join)
        response = client.get(reverse("entities:person-documents", args=(person.slug,)))
        assert "2 related documents" in response.context["page_description"]

    def test_get_related(self, client, document, multifragment):
        # attach a person to two documents
        person = Person.objects.create(has_page=True)
        Name.objects.create(name="Goitein", content_object=person, primary=True)
        person.generate_slug()
        person.save()
        # first document is a Legal document, with relation Author
        author = PersonDocumentRelationType.objects.get_or_create(name_en="Author")[0]
        legal_doc_relation = PersonDocumentRelation.objects.create(
            document=document, person=person, type=author
        )

        # second document is a State document, with relation Recipient
        state_doc = Document.objects.create(
            doctype=DocumentType.objects.get_or_create(name_en="State")[0]
        )
        TextBlock.objects.create(document=state_doc, fragment=multifragment)
        state_doc_relation = PersonDocumentRelation.objects.create(
            person=person,
            document=state_doc,
            type=PersonDocumentRelationType.objects.get_or_create(name_en="Recipient")[
                0
            ],
        )

        # get_related should return an iterable with both documents
        response = client.get(reverse("entities:person-documents", args=(person.slug,)))
        related_docs_list = response.context.get("related_documents")
        related_doc_pks = [doc["pk"] for doc in related_docs_list]
        assert document.pk in related_doc_pks
        assert state_doc.pk in related_doc_pks

        # by default, should sort alphabetically by shelfmark, ascending
        assert response.context.get("sort") == "shelfmark_asc"
        # legal doc shelfmark starts with CUL, state doc shelfmark starts with T-S
        assert related_docs_list[0]["pk"] == legal_doc_relation.document.pk

        # sort alphabetically by shelfmark, descending
        response = client.get(
            reverse("entities:person-documents", args=(person.slug,)),
            {"sort": "shelfmark_desc"},
        )
        related_docs_list = response.context.get("related_documents")
        assert related_docs_list[0]["pk"] == state_doc_relation.document.pk

        # sort alphabetically by doctype, ascending (Legal, then State)
        response = client.get(
            reverse("entities:person-documents", args=(person.slug,)),
            {"sort": "doctype_asc"},
        )
        related_docs_list = response.context.get("related_documents")
        assert related_docs_list[0]["pk"] == legal_doc_relation.document.pk

        # sort alphabetically by relation, ascending (Author, then Recipient)
        response = client.get(
            reverse("entities:person-documents", args=(person.slug,)),
            {"sort": "relation_asc"},
        )
        related_docs_list = response.context.get("related_documents")
        assert related_docs_list[0]["pk"] == legal_doc_relation.document.pk

        # add some on-document and inferred dates to the documents
        document.doc_date_original = "5 Elul 5567"
        document.doc_date_calendar = Calendar.ANNO_MUNDI
        document.doc_date_standard = "1807-09-08"
        document.save()
        Dating.objects.create(
            document=state_doc,
            display_date="1800 CE",
            standard_date="1800",
            rationale=Dating.PALEOGRAPHY,
            notes="a note",
        )
        undated_doc = Document.objects.create()
        undated_doc_relation = PersonDocumentRelation.objects.create(
            document=undated_doc, person=person, type=author
        )

        # sort by date ascending
        response = client.get(
            reverse("entities:person-documents", args=(person.slug,)),
            {"sort": "date_asc"},
        )
        related_docs_list = response.context.get("related_documents")
        # date sort returns a list due to additional calculations needed
        assert related_docs_list[0]["pk"] == state_doc_relation.document.pk
        # undated should be sorted last
        assert related_docs_list[-1]["pk"] == undated_doc_relation.document.pk
        # sort by date descending
        response = client.get(
            reverse("entities:person-documents", args=(person.slug,)),
            {"sort": "date_desc"},
        )
        related_docs_list = response.context.get("related_documents")
        assert related_docs_list[0]["pk"] == legal_doc_relation.document.pk
        # undated should still be sorted last
        assert related_docs_list[-1]["pk"] == undated_doc_relation.document.pk

    def test_get_context_data(self, client):
        # should 404 when no documents related to person
        person = Person.objects.create(has_page=True)
        Name.objects.create(name="test", content_object=person, primary=True)
        person.generate_slug()
        person.save()
        response = client.get(reverse("entities:person-documents", args=(person.slug,)))
        assert response.status_code == 404


@pytest.mark.django_db
class TestPersonPeopleView:
    def test_page_description(self, client, person, person_diacritic, person_multiname):
        person.has_page = True
        person.save()
        # add some related people
        parent_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="parent", converse_name_en="child"
        )
        PersonPersonRelation.objects.create(
            from_person=person, to_person=person_diacritic, type=parent_type
        )
        grandchild_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="grandchild", converse_name_en="grandparent"
        )
        PersonPersonRelation.objects.create(
            from_person=person, to_person=person_multiname, type=grandchild_type
        )
        response = client.get(reverse("entities:person-people", args=(person.slug,)))
        assert response.context["page_description"] == "2 related people"

    def test_get_related(
        self, client, document, person, person_diacritic, person_multiname
    ):
        person.has_page = True
        person.save()
        # add some related people
        parent_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="parent", converse_name_en="child"
        )
        PersonPersonRelation.objects.create(
            from_person=person, to_person=person_diacritic, type=parent_type
        )
        grandchild_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="grandchild", converse_name_en="grandparent"
        )
        PersonPersonRelation.objects.create(
            from_person=person, to_person=person_multiname, type=grandchild_type
        )
        response = client.get(reverse("entities:person-people", args=(person.slug,)))
        assert any(
            [
                r["id"] == person_diacritic.pk and r["type"].lower() == "parent"
                for r in response.context["related_people"]
            ]
        )
        assert any(
            [
                r["id"] == person_multiname.pk and r["type"].lower() == "grandchild"
                for r in response.context["related_people"]
            ]
        )
        # should sort by name, asc by default
        assert response.context["related_people"][0]["id"] == person_diacritic.pk
        # can also sort by name, desc
        response = client.get(
            reverse("entities:person-people", args=(person.slug,)),
            {"sort": "name_desc"},
        )
        assert response.context["related_people"][0]["id"] == person_multiname.pk

        # sort by relation type
        response = client.get(
            reverse("entities:person-people", args=(person.slug,)),
            {"sort": "relation_asc"},
        )
        assert response.context["related_people"][0]["type"].lower() == "grandchild"

        # add shared documents
        PersonDocumentRelation.objects.create(person=person, document=document)
        PersonDocumentRelation.objects.create(
            person=person_multiname, document=document
        )
        response = client.get(
            reverse("entities:person-people", args=(person.slug,)),
            {"sort": "documents_desc"},
        )
        assert response.context["related_people"][0]["id"] == person_multiname.pk
        assert response.context["related_people"][0]["shared_documents"] == 1
        assert response.context["related_people"][1]["shared_documents"] == 0

    def test_get_context_data(self, client, person, person_diacritic):
        # test relation categories context variable
        person.has_page = True
        person.save()
        response = client.get(reverse("entities:person-people", args=(person.slug,)))
        parent_type, _ = PersonPersonRelationType.objects.get_or_create(
            name_en="Parent",
            converse_name_en="Child",
            category=PersonPersonRelationType.IMMEDIATE_FAMILY,
        )
        PersonPersonRelation.objects.create(
            from_person=person, to_person=person_diacritic, type=parent_type
        )
        assert (
            response.context["relation_categories"]["Parent"]
            == PersonPersonRelationType.IMMEDIATE_FAMILY
        )
        assert (
            response.context["relation_categories"]["Child"]
            == PersonPersonRelationType.IMMEDIATE_FAMILY
        )


@pytest.mark.django_db
class TestPersonPlacesView:
    def test_page_title(self, client):
        person = Person.objects.create(has_page=True, slug="goitein")
        place = Place.objects.create()
        PersonPlaceRelation.objects.create(person=person, place=place)
        response = client.get(reverse("entities:person-places", args=(person.slug,)))
        assert response.context["page_title"] == f"Related places for {str(person)}"

    def test_page_description(self, client):
        # should use number of places as page description
        person = Person.objects.create(has_page=True, slug="goitein")
        place = Place.objects.create()
        PersonPlaceRelation.objects.create(person=person, place=place)
        place2 = Place.objects.create()
        PersonPlaceRelation.objects.create(person=person, place=place2)
        response = client.get(reverse("entities:person-places", args=(person.slug,)))
        assert response.context["page_description"] == "2 related places"

    def test_get_related(self, client):
        # create some relations
        person = Person.objects.create(has_page=True, slug="goitein")
        aydhab = Place.objects.create(slug="aydhab")
        Name.objects.create(name="ʿAydhāb", content_object=aydhab, primary=True)
        (oct, _) = PersonPlaceRelationType.objects.get_or_create(
            name="Occasional trips to"
        )
        aydhab_relation = PersonPlaceRelation.objects.create(
            person=person, place=aydhab, type=oct
        )
        fustat = Place.objects.create(slug="fustat")
        Name.objects.create(name="Fustat", content_object=fustat, primary=True)
        (hb, _) = PersonPlaceRelationType.objects.get_or_create(name="Home base")
        fustat_relation = PersonPlaceRelation.objects.create(
            person=person, place=fustat, type=hb
        )
        response = client.get(reverse("entities:person-places", args=(person.slug,)))

        # all should be present
        assert aydhab_relation in response.context["related_places"]
        assert fustat_relation in response.context["related_places"]

        # aydhab should be first: alphabetical by slug by default
        assert response.context["related_places"].first().pk == aydhab_relation.pk

        # sort by name/slug descending
        response = client.get(
            reverse("entities:person-places", args=(person.slug,)),
            {"sort": "name_desc"},
        )
        assert response.context["related_places"].first().pk == fustat_relation.pk

        # sort by relation type ascending
        response = client.get(
            reverse("entities:person-places", args=(person.slug,)),
            {"sort": "relation_asc"},
        )
        assert response.context["related_places"].first().pk == fustat_relation.pk

    @override_settings(MAPTILER_API_TOKEN="example")
    def test_get_context_data(self, client):
        # no related places, should 404
        person = Person.objects.create(has_page=True, slug="goitein")
        response = client.get(reverse("entities:person-places", args=(person.slug,)))
        assert response.status_code == 404

        # related places, should 200
        place = Place.objects.create(slug="test")
        relation = PersonPlaceRelation.objects.create(person=person, place=place)

        response = client.get(reverse("entities:person-places", args=(person.slug,)))
        assert response.status_code == 200
        # context should inherit "page_type": "person"
        assert response.context["page_type"] == "person"
        # context should include the maptiler token if one exists in settings
        assert response.context["maptiler_token"] == "example"
        # context should include the related places
        assert relation in response.context["related_places"]


@pytest.mark.django_db
class TestPlacePeopleView:
    def test_page_title(self, client):
        person = Person.objects.create()
        place = Place.objects.create(slug="place")
        PersonPlaceRelation.objects.create(person=person, place=place)
        response = client.get(reverse("entities:place-people", args=(place.slug,)))
        assert response.context["page_title"] == f"Related people for {str(place)}"

    def test_page_description(self, client):
        # should use number of people as page description
        person = Person.objects.create()
        person2 = Person.objects.create()
        place = Place.objects.create(slug="place")
        PersonPlaceRelation.objects.create(person=person, place=place)
        PersonPlaceRelation.objects.create(person=person2, place=place)
        response = client.get(reverse("entities:place-people", args=(place.slug,)))
        assert response.context["page_description"] == "2 related people"

    def test_get_related(self, client):
        # create some relations
        fustat = Place.objects.create(slug="fustat")
        nahray = Person.objects.create(slug="nahray")
        Name.objects.create(
            name="Nahray b. Nissim", content_object=nahray, primary=True
        )
        (oct, _) = PersonPlaceRelationType.objects.get_or_create(
            name="Occasional trips to"
        )
        nahray_relation = PersonPlaceRelation.objects.create(
            person=nahray, place=fustat, type=oct
        )
        ezra = Person.objects.create(slug="ezra-b-hillel")
        Name.objects.create(name="ʿEzra b. Hillel", content_object=ezra, primary=True)
        (hb, _) = PersonPlaceRelationType.objects.get_or_create(name="Home base")
        ezra_relation = PersonPlaceRelation.objects.create(
            person=ezra, place=fustat, type=hb
        )
        response = client.get(reverse("entities:place-people", args=(fustat.slug,)))

        # all should be present
        assert ezra_relation in response.context["related_people"]
        assert nahray_relation in response.context["related_people"]

        # ezra should be first: alphabetical by slug by default
        assert response.context["related_people"].first().pk == ezra_relation.pk

        # sort by name/slug descending
        response = client.get(
            reverse("entities:place-people", args=(fustat.slug,)),
            {"sort": "name_desc"},
        )
        assert response.context["related_people"].first().pk == nahray_relation.pk

        # sort by relation type ascending
        response = client.get(
            reverse("entities:place-people", args=(fustat.slug,)),
            {"sort": "relation_asc"},
        )
        assert response.context["related_people"].first().pk == ezra_relation.pk

    @override_settings(MAPTILER_API_TOKEN="example")
    def test_get_context_data(self, client):
        # no related people, should 404
        place = Place.objects.create(slug="place")
        response = client.get(reverse("entities:place-people", args=(place.slug,)))
        assert response.status_code == 404

        # related places, should 200
        person = Person.objects.create()
        relation = PersonPlaceRelation.objects.create(person=person, place=place)

        response = client.get(reverse("entities:place-people", args=(place.slug,)))
        assert response.status_code == 200
        # context should inherit "page_type": "place"
        assert response.context["page_type"] == "place"
        # context should include the related person
        assert relation in response.context["related_people"]


@pytest.mark.django_db
class TestPlaceListView:
    def test_get_form_kwargs(self):
        placelist_view = PlaceListView()
        placelist_view.request = Mock()
        placelist_view.get_range_stats = Mock(return_value={})

        # no params
        placelist_view.request.GET = {}
        kwargs = placelist_view.get_form_kwargs()
        assert kwargs["initial"] == PlaceListView.initial
        assert kwargs["data"] == PlaceListView.initial

        # sort param
        placelist_view.request.GET = {"sort": "documents", "sort_dir": "desc"}
        kwargs = placelist_view.get_form_kwargs()
        assert kwargs["initial"] == PlaceListView.initial
        assert kwargs["data"] == {"sort": "documents", "sort_dir": "desc"}

        # range_stats date range rounding
        placelist_view.get_range_stats.return_value = {"date_range": (890, 1967)}
        kwargs = placelist_view.get_form_kwargs()
        # should round lower date down, upper date up
        assert kwargs["range_minmax"]["date_range"][0] == 800
        assert kwargs["range_minmax"]["date_range"][1] == 2000

    @pytest.mark.usefixtures("mock_solr_queryset")
    @patch("geniza.entities.views.PlaceListView.get_queryset")
    def test_get_context_data(self, mock_get_queryset, rf, mock_solr_queryset):
        with patch(
            "geniza.entities.views.PlaceSolrQuerySet",
            new=mock_solr_queryset(PlaceSolrQuerySet),
        ) as mock_queryset_cls:
            mock_qs = mock_queryset_cls.return_value
            mock_get_queryset.return_value = mock_qs
            placelist_view = PlaceListView(kwargs={})
            placelist_view.queryset = mock_qs
            placelist_view.object_list = mock_qs
            placelist_view.request = rf.get("/places/")
            placelist_view.get_range_stats = Mock(return_value={})
            context_data = placelist_view.get_context_data()
            assert context_data["page_type"] == "places"
            assert context_data["search_opts"]["form_valid"] == True

            # total count should be pulled from SolrQuerySet
            mock_qs.count.assert_called()

            # invalid form
            placelist_view.request.GET = {"sort": "abcdefg"}
            context_data = placelist_view.get_context_data()
            assert context_data["search_opts"]["form_valid"] == False

            # should resolve desc sort
            placelist_view.request.GET = {"sort": "name", "sort_dir": "desc"}
            context_data = placelist_view.get_context_data()
            assert "order_by" in context_data["search_opts"]
            assert context_data["search_opts"]["order_by"] == "-slug_s"
            assert "query" not in context_data["search_opts"]

            # should pass query to search opts
            placelist_view.request.GET = {
                "q": "cairo",
                "sort": "relevance",
                "sort_dir": "desc",
            }
            context_data = placelist_view.get_context_data()
            assert context_data["search_opts"]["order_by"] == "-score"
            assert "query" in context_data["search_opts"]
            assert context_data["search_opts"]["query"] == "cairo"
            assert len(context_data["applied_filters"]) == 0

            # date filter
            placelist_view.get_form = Mock()
            placelist_view.get_form.return_value.cleaned_data = {
                "date_range": (800, None)
            }
            context_data = placelist_view.get_context_data()
            assert context_data["search_opts"]["date_range"] == (800, None)
            assert len(context_data["applied_filters"]) == 1


@pytest.mark.django_db
class TesttPlaceListSnippetView:
    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_get(self, rf, mock_solr_queryset):
        with patch(
            "geniza.entities.views.PlaceSolrQuerySet",
            new=self.mock_solr_queryset(PlaceSolrQuerySet),
        ) as mock_queryset_cls:
            mock_qs = mock_queryset_cls.return_value
            mock_qs.keyword_search.return_value = mock_qs
            mock_qs.also.return_value = mock_qs
            mock_qs.order_by.return_value = mock_qs

            # simulate two pages of results (150 results, 100 per page)
            mock_qs.count.return_value = 150
            mock_qs.__len__.return_value = 150
            mock_places = [
                # set '"location" in p' conditional always true
                MagicMock(**{"__contains__.return_value": True})
                for _ in range(150)
            ]
            mock_qs.__getitem__.side_effect = lambda i: mock_places[i]

            # test search options
            snippet_view = PlaceListSnippetView()
            snippet_view.request = rf.get("/place-snippets/")
            snippet_view.request.GET = {"q": "qa'id", "sort": "-score"}

            json_resp = snippet_view.get()
            data = json.loads(json_resp.content)
            mock_qs.keyword_search.assert_called_with("qaid")
            mock_qs.order_by.assert_called_with("-score")
            assert data["results_count"] == "150 results"
            assert data["places_count"] == "150 places"

            # test pagination
            snippet_view.request.GET = {"page": "1"}
            json_resp = snippet_view.get()
            data = json.loads(json_resp.content)
            assert data["has_next"] == True
            assert data["next_page_number"] == 2
            assert 'data-final="true"' not in data["markers_snippet"]

            snippet_view.request.GET = {"page": "2"}
            json_resp = snippet_view.get()
            data = json.loads(json_resp.content)
            assert data["has_next"] == False
            assert not data["next_page_number"]
            assert 'data-final="true"' in data["markers_snippet"]

            snippet_view.request.GET = {"page": "100"}
            json_resp = snippet_view.get()
            data = json.loads(json_resp.content)
            # should fallback to final page (2)
            assert data["has_next"] == False
            assert not data["next_page_number"]
            assert 'data-final="true"' in data["markers_snippet"]
            mock_qs.filter.assert_not_called

            # test date filter
            snippet_view.request.GET = {"date_range": "800,1200"}
            snippet_view.get()
            mock_qs.filter.assert_called_with(
                "{!join from=places_ids_ss to=id}item_type_s:document AND document_date_dr:[800 TO 1200]"
            )
            snippet_view.request.GET = {"date_range": "800,"}
            snippet_view.get()
            mock_qs.filter.assert_called_with(
                "{!join from=places_ids_ss to=id}item_type_s:document AND document_date_dr:[800 TO *]"
            )
            snippet_view.request.GET = {"date_range": ",1200"}
            snippet_view.get()
            mock_qs.filter.assert_called_with(
                "{!join from=places_ids_ss to=id}item_type_s:document AND document_date_dr:[* TO 1200]"
            )
