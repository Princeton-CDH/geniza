import time
from unittest.mock import Mock, patch

import pytest
from django.contrib import admin
from django.db.models.query import EmptyQuerySet
from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.test import RequestFactory
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from geniza.corpus.dates import standard_date_display
from geniza.corpus.models import Dating, Document, LanguageScript
from geniza.entities.admin import (
    NameInlineFormSet,
    PersonAdmin,
    PersonDocumentInline,
    PersonDocumentRelationTypeAdmin,
    PersonPersonInline,
    PersonPersonRelationTypeChoiceField,
    PersonPersonReverseInline,
    PlaceAdmin,
    PlacePlaceReverseInline,
)
from geniza.entities.models import (
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    Place,
    PlacePlaceRelation,
    PlacePlaceRelationType,
    Region,
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

    def test_dating_range(self):
        goitein = Person.objects.create()
        doc = Document.objects.create()
        relation = PersonDocumentRelation.objects.create(person=goitein, document=doc)
        inline = PersonDocumentInline(goitein, admin_site=admin.site)
        assert inline.dating_range(relation) == "-"

        Dating.objects.create(standard_date="1000/1010", document=doc)
        assert inline.dating_range(relation) == "1000–1010 CE"


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

    def test_merge_people(self):
        mockrequest = Mock()
        test_ids = ["50344", "33003", "10100"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = PersonAdmin(Person, Mock()).merge_people(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 303
        assert resp["location"].startswith(reverse("admin:person-merge"))
        assert resp["location"].endswith("?ids=%s" % ",".join(test_ids))

        test_ids = ["50344"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = PersonAdmin(Person, Mock()).merge_people(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 302
        assert resp["location"] == reverse("admin:entities_person_changelist")

    def test_save_related(self):
        # if a person does not have a slug, the form should generate one after related_save
        # (i.e. the Name association has been saved)
        person = Person.objects.create()
        Name.objects.create(name="Goitein", content_object=person)
        assert not person.slug
        # mock all arguments to admin method; form.instance should be our person
        mockform = Mock()
        mockform.instance = person
        with patch.object(admin.ModelAdmin, "save_related"):
            PersonAdmin(Person, Mock()).save_related(Mock(), mockform, Mock(), Mock())
        assert person.slug

    @pytest.mark.django_db
    def test_export_to_csv(self, person, person_multiname):
        # adapted from document csv export tests
        person_multiname.description = "Test description"
        person_multiname.save()
        person_admin = PersonAdmin(model=Person, admin_site=admin.site)
        response = person_admin.export_to_csv(Mock())
        assert isinstance(response, StreamingHttpResponse)
        # consume the binary streaming content and decode to inspect as str
        content = b"".join([val for val in response.streaming_content]).decode()

        # spot-check that we get expected data
        # - header row
        assert "name,name_variants," in content
        # - some content
        assert str(person) in content
        assert person.description in content
        assert str(person_multiname) in content
        assert person_multiname.description in content

    @pytest.mark.django_db
    def test_export_relations_to_csv(self, person, person_multiname):
        (partner, _) = PersonPersonRelationType.objects.get_or_create(
            name_en="Partner", category=PersonPersonRelationType.BUSINESS
        )
        PersonPersonRelation.objects.create(
            from_person=person, to_person=person_multiname, type=partner
        )
        # adapted from document csv export tests
        person_admin = PersonAdmin(model=Person, admin_site=admin.site)
        response = person_admin.export_relations_to_csv(Mock(), pk=person.pk)
        assert isinstance(response, StreamingHttpResponse)
        # consume the binary streaming content and decode to inspect as str
        content = b"".join([val for val in response.streaming_content]).decode()

        # spot-check that we get expected data
        # - header row
        assert "related_object_type,related_object_id," in content
        # - some content
        assert str(person) in content
        assert str(person_multiname) in content
        assert "Partner" in content

    def test_date_ranges(self, person, document, join):
        document.doc_date_standard = "1200/1300"
        document.save()
        (pdrtype, _) = PersonDocumentRelationType.objects.get_or_create(name="test")
        PersonDocumentRelation.objects.create(
            person=person, document=document, type=pdrtype
        )
        (deceased, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Mentioned (deceased)"
        )
        join.doc_date_standard = "1310/1312"
        join.save()
        PersonDocumentRelation.objects.create(
            person=person, document=join, type=deceased
        )

        person_admin = PersonAdmin(model=Person, admin_site=admin.site)
        assert person_admin.active_dates(person) == standard_date_display(
            document.doc_date_standard
        )
        assert person_admin.deceased_mention_dates(person) == standard_date_display(
            join.doc_date_standard
        )

    def test_get_search_results(self, person, person_multiname, empty_solr):
        # adapted from TestDocumentAdmin.test_get_search_results
        # index fixture data in solr
        Person.index_items([person, person_multiname])
        time.sleep(1)

        pers_admin = PersonAdmin(model=Person, admin_site=admin.site)
        queryset, needs_distinct = pers_admin.get_search_results(
            Mock(), Person.objects.all(), "bogus"
        )
        assert not queryset.count()
        assert not needs_distinct
        assert isinstance(queryset, EmptyQuerySet)

        queryset, needs_distinct = pers_admin.get_search_results(
            Mock(), Person.objects.all(), "Yijū"
        )
        assert queryset.count() == 1
        assert isinstance(queryset.first(), Person)
        queryset, needs_distinct = pers_admin.get_search_results(
            Mock(), Person.objects.all(), "yiju"
        )
        assert queryset.count() == 1

        # should find by secondary name
        queryset, needs_distinct = pers_admin.get_search_results(
            Mock(), Person.objects.all(), "Apple"
        )
        assert queryset.count() == 1

        # empty search term should return all records
        queryset, needs_distinct = pers_admin.get_search_results(
            Mock(), Person.objects.all(), ""
        )
        assert queryset.count() == Person.objects.all().count()


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

        # should raise validation error if exactly one primary name and DELETE is checked
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
                "entities-name-content_type-object_id-0-DELETE": "on",
                "entities-name-content_type-object_id-1-name": "S.D. Goitein",
                "entities-name-content_type-object_id-1-language": str(english.pk),
                "entities-name-content_type-object_id-1-transliteration_style": Name.NONE,
            },
        )
        assertContains(response, NameInlineFormSet.DISPLAY_NAME_ERROR)


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


class TestPlaceEventInline:
    def test_get_formset(self, admin_client):
        # there should be no link to a popup to add an event from the Person admin
        url = reverse("admin:entities_place_add")
        response = admin_client.get(url)
        content = str(response.content)
        # NOTE: confirmed the following assertion fails when get_formset not overridden
        assert "Add another event" not in content


class TestEventDocumentInline:
    def test_get_min_num(self, admin_client, document):
        # it should be required to add at least one document from the Event admin
        response = admin_client.get(reverse("admin:entities_event_add"))
        content = str(response.content)
        assert 'name="documenteventrelation_set-MIN_NUM_FORMS" value="1"' in content

        # however, when accessed via popup from the Document admin, this requirement
        # should be removed
        response = admin_client.get(
            reverse("admin:entities_event_add"), {"from_document": "true"}
        )
        content = str(response.content)
        assert 'name="documenteventrelation_set-MIN_NUM_FORMS" value="0"' in content


@pytest.mark.django_db
class TestPlacePlaceReverseInline:
    def test_relation(self):
        # should show converse relationship type when available
        (neighborhood, _) = PlacePlaceRelationType.objects.get_or_create(
            name="Neighborhood",
            converse_name="City",
        )
        fustat = Place.objects.create()
        qasr = Place.objects.create()
        rel = PlacePlaceRelation.objects.create(
            place_a=fustat,
            place_b=qasr,
            type=neighborhood,
        )
        reverse_inline = PlacePlaceReverseInline(Place, admin_site=admin.site)
        assert reverse_inline.relation(rel) == neighborhood.converse_name

        # otherwise should just show relationship type
        (same, _) = PlacePlaceRelationType.objects.get_or_create(
            name="Possibly the same as",
        )
        fust2 = Place.objects.create()
        rel = PlacePlaceRelation.objects.create(
            place_a=fustat,
            place_b=fust2,
            type=same,
        )
        assert reverse_inline.relation(rel) == same.name


@pytest.mark.django_db
class TestPlaceAdmin:
    def test_save_related(self):
        # if a place does not have a slug, the form should generate one after related_save
        # (i.e. the Name association has been saved)
        place = Place.objects.create()
        Name.objects.create(name="Fusṭāṭ", content_object=place)
        assert not place.slug
        # mock all arguments to admin method; form.instance should be our place
        mockform = Mock()
        mockform.instance = place
        with patch.object(admin.ModelAdmin, "save_related"):
            PlaceAdmin(Place, Mock()).save_related(Mock(), mockform, Mock(), Mock())
        assert place.slug

    def test_get_queryset(self):
        # create a place
        place = Place.objects.create()
        Name.objects.create(name="Fusṭāṭ", content_object=place, primary=True)
        place_admin = PlaceAdmin(Place, admin_site=admin.site)

        # queryset should include name_unaccented field without diacritics
        qs = place_admin.get_queryset(Mock())
        assert qs.filter(name_unaccented__icontains="fustat").exists()

    @pytest.mark.django_db
    def test_export_to_csv(self):
        # adapted from document csv export tests
        mosul = Place.objects.create(slug="mosul", notes="A city in Iraq")
        Name.objects.create(content_object=mosul, name="Mosul", primary=True)
        egypt_region = Region.objects.create(name="Egypt")
        fustat = Place.objects.create(slug="fustat", containing_region=egypt_region)
        Name.objects.create(content_object=fustat, name="Fusṭāṭ", primary=True)
        abyssinia = Place.objects.create(slug="abyssinia-region", is_region=True)
        Name.objects.create(
            name="Abyssinia (region)", content_object=abyssinia, primary=True
        )

        place_admin = PlaceAdmin(model=Place, admin_site=admin.site)
        response = place_admin.export_to_csv(Mock())
        assert isinstance(response, StreamingHttpResponse)
        # consume the binary streaming content and decode to inspect as str
        content = b"".join([val for val in response.streaming_content]).decode()

        # spot-check that we get expected data
        # - header row
        assert "name,name_variants," in content
        is_region_idx = content.split(",").index("is_region")
        # - some content
        assert str(mosul) in content
        assert str(fustat) in content
        assert str(abyssinia) in content
        for row in content.split("\n"):
            if str(mosul) in row:
                assert mosul.notes in row
            elif str(fustat) in row:
                assert fustat.permalink in row
                assert str(egypt_region) in row
                assert row.split(",")[is_region_idx] == "N"
            elif str(abyssinia) in row:
                assert str(egypt_region) not in row
                assert row.split(",")[is_region_idx] == "Y"

    @pytest.mark.django_db
    def test_export_relations_to_csv(self, person):
        fustat = Place.objects.create(slug="fustat")
        Name.objects.create(content_object=fustat, name="Fusṭāṭ", primary=True)
        (home_base, _) = PersonPlaceRelationType.objects.get_or_create(name="Home base")
        PersonPlaceRelation.objects.create(person=person, place=fustat, type=home_base)
        # adapted from document csv export tests
        place_admin = PlaceAdmin(model=Place, admin_site=admin.site)
        response = place_admin.export_relations_to_csv(Mock(), pk=fustat.pk)
        assert isinstance(response, StreamingHttpResponse)
        # consume the binary streaming content and decode to inspect as str
        content = b"".join([val for val in response.streaming_content]).decode()

        # spot-check that we get expected data
        # - header row
        assert "related_object_type,related_object_id," in content
        # - some content
        assert str(person) in content
        assert "Home base" in content


class TestPersonDocumentRelationTypeAdmin:
    def test_merge_person_document_relation_types(self):
        pdr_admin = PersonDocumentRelationTypeAdmin(
            model=PersonDocumentRelationType, admin_site=admin.site
        )
        mockrequest = Mock()
        test_ids = ["1", "2", "3"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = pdr_admin.merge_relation_types(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 303
        assert resp["location"].startswith(
            reverse("admin:person-document-relation-type-merge")
        )
        assert resp["location"].endswith("?ids=%s" % ",".join(test_ids))

        test_ids = ["1"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = pdr_admin.merge_relation_types(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 302
        assert resp["location"] == reverse(
            "admin:entities_persondocumentrelationtype_changelist"
        )
