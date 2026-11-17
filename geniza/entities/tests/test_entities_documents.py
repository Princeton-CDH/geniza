import datetime

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from pytest_django.asserts import assertContains

from geniza.corpus.metadata_export import DocumentExporter
from geniza.corpus.models import Document
from geniza.entities.models import (
    DocumentEventRelation,
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Event,
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    Place,
)

# tests for entity relationships on corpus documents, moved from geniza.corpus
# so corpus tests can run without geniza.entities installed


@pytest.mark.django_db
def test_document_merge_with_related_entities(
    document, join, person, person_diacritic, person_multiname
):
    # add person-document relationships
    mentioned, _ = PersonDocumentRelationType.objects.get_or_create(name="Mentioned")
    author, _ = PersonDocumentRelationType.objects.get_or_create(name="Author")
    recipient, _ = PersonDocumentRelationType.objects.get_or_create(name="Recipient")
    # same person and type, different notes
    mentioned_rel = PersonDocumentRelation.objects.create(
        document=document, person=person, type=mentioned, notes="Mentioned on line 5."
    )
    merged_mentioned_rel = PersonDocumentRelation.objects.create(
        document=join, person=person, type=mentioned, notes="Sourced from evidence."
    )
    # same person, different type
    PersonDocumentRelation.objects.create(
        document=document,
        person=person_diacritic,
        type=author,
        notes="Authored similar.",
    )
    newtype_rel = PersonDocumentRelation.objects.create(
        document=join, person=person_diacritic, type=recipient, notes="Address on top."
    )
    # different person
    newperson_rel = PersonDocumentRelation.objects.create(
        document=join,
        person=person_multiname,
        type=recipient,
        notes="Also address on top.",
    )

    assert document.persondocumentrelation_set.count() == 2

    # merge into document as primary
    join_pk = join.pk
    document.merge_with([join], "test")

    # should have added Recipient relation with person_diacritic, and relationship with person_multiname
    assert document.persondocumentrelation_set.count() == 4

    # notes should be merged on person + type matches
    old_notes = mentioned_rel.notes
    mentioned_rel.refresh_from_db()
    assert (
        mentioned_rel.notes
        == f"{old_notes}\nNotes from PGPID {join_pk}: {merged_mentioned_rel.notes}"
    )

    # duplicate relation should be cascade-deleted
    assert not PersonDocumentRelation.objects.filter(
        pk=merged_mentioned_rel.pk
    ).exists()

    # otherwise should just reassign relationships to primary document
    newtype_rel.refresh_from_db()
    assert newtype_rel.document.pk == document.pk
    newperson_rel.refresh_from_db()
    assert newperson_rel.document.pk == document.pk

    # ensure basic merge functionality works for places and events too
    # (uses the same logic as people so no need to test in depth)
    doc3 = Document.objects.create()
    fustat = Place.objects.create()
    qasr = Place.objects.create()
    pdr_type = DocumentPlaceRelationType.objects.create()
    DocumentPlaceRelation.objects.create(document=document, place=fustat, type=pdr_type)
    DocumentPlaceRelation.objects.create(document=doc3, place=fustat, type=pdr_type)
    DocumentPlaceRelation.objects.create(document=doc3, place=qasr, type=pdr_type)
    assert document.documentplacerelation_set.count() == 1
    document.merge_with([doc3], "test")
    assert document.documentplacerelation_set.count() == 2

    doc4 = Document.objects.create()
    publication = Event.objects.create()
    founding = Event.objects.create()
    DocumentEventRelation.objects.create(document=document, event=publication)
    DocumentEventRelation.objects.create(document=doc4, event=founding)
    assert document.documenteventrelation_set.count() == 1
    document.merge_with([doc4], "test")
    assert document.documenteventrelation_set.count() == 2


@pytest.mark.django_db
class TestDocumentEventRelation:
    def test_str(self, document):
        event = Event.objects.create(name="Founding of the Ben Ezra Synagogue")
        relation = DocumentEventRelation.objects.create(document=document, event=event)
        assert str(relation) == f"Document-Event relation: {document} and {event}"


@pytest.mark.django_db
class TestDocumentDetailViewEntities:
    def test_related_people_places(self, client, document):
        response = client.get(reverse("corpus:document", args=(document.pk,)))
        # related people and places should be empty querysets
        assert response.context["related_people"].count() == 0
        assert response.context["related_places"].count() == 0

        # add related people
        abu = Person.objects.create(slug="abu-imran")
        ezra = Person.objects.create(slug="ezra-b-hillel")
        nahray = Person.objects.create(slug="nahray")
        (author, _) = PersonDocumentRelationType.objects.get_or_create(name="Author")
        (recipient, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Recipient"
        )
        PersonDocumentRelation.objects.create(
            person=ezra, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=abu, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=nahray, type=author, document=document
        )
        response = client.get(reverse("corpus:document", args=(document.pk,)))
        assert response.context["related_people"].count() == 3
        # should sort alphabetically by type, then slug (name)
        assert response.context["related_people"].first().person.pk == nahray.pk
        assert response.context["related_people"][1].person.pk == abu.pk

        # add related place
        fustat = Place.objects.create(slug="fustat")
        DocumentPlaceRelation.objects.create(place=fustat, document=document)
        assert response.context["related_places"].count() == 1
        assert response.context["related_places"].first().place.pk == fustat.pk

    def test_related_entities(
        self, client, document, person, person_diacritic, person_multiname
    ):
        # add related people
        person.has_page = True
        person.save()
        (author, _) = PersonDocumentRelationType.objects.get_or_create(name="Author")
        (recipient, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Recipient"
        )
        PersonDocumentRelation.objects.create(
            person=person_multiname, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=person_diacritic, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=person, type=author, document=document
        )
        # add related place
        fustat = Place.objects.create(slug="fustat")
        DocumentPlaceRelation.objects.create(place=fustat, document=document)

        # should group "recipient" people together and join their names by comma
        response = client.get(reverse("corpus:document", args=(document.pk,)))
        # should be "Halfon, Zed" = recipients
        print(response.content.decode("utf-8"))
        assertContains(response, f"{person_diacritic}", html=True)
        assertContains(response, f"{person_multiname}", html=True)
        # should link to author because has_page=True
        assertContains(
            response, f'<a data-turbo="false" href="{person.get_absolute_url()}">'
        )
        # should link to place
        assertContains(
            response, f'<a data-turbo="false" href="{fustat.get_absolute_url()}">'
        )


@pytest.mark.django_db
def test_export_doc_places(document):

    mosul = Place.objects.create(slug="mosul")
    Name.objects.create(content_object=mosul, name="Mosul", primary=True)
    Name.objects.create(content_object=mosul, name="الموصل", primary=False)
    fustat = Place.objects.create(slug="fustat")
    Name.objects.create(content_object=fustat, name="Fustat", primary=True)

    (dest, _) = DocumentPlaceRelationType.objects.get_or_create(name="Destination")
    (ment, _) = DocumentPlaceRelationType.objects.get_or_create(
        name="Possibly mentioned"
    )

    DocumentPlaceRelation.objects.create(place=mosul, type=dest, document=document)
    DocumentPlaceRelation.objects.create(place=fustat, type=ment, document=document)

    doc_qs = Document.objects.all().order_by("id")
    exporter = DocumentExporter(queryset=doc_qs)
    print(exporter.iter_dicts())
    for export_data in exporter.iter_dicts():
        assert "Mosul" in export_data.get("destination")
        assert "Fustat" in export_data.get("possibly_mentioned")


class TestPersonDate:

    def test_clean(self):
        person = Person()
        # no dates; no error
        person.clean()

        # full past date — no error
        person.date = "2024-06-12"
        person.clean()

        # full past date range — no error
        person.date = "2024-06-12/2025-06-12"
        person.clean()

        # full past date range with end earlier than start —  error
        person.date = "2025-06-12/2024-06-12"
        with pytest.raises(ValidationError):
            person.clean()

        # partial past date — no error
        person.date = "2024"
        person.clean()

        # partial past date range — no error
        person.date = "2024/2025"
        person.clean()

        # partial past date range with end earlier than start — error
        person.date = "2025/2024"
        with pytest.raises(ValidationError):
            person.clean()

        # future date - error
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        person.date = tomorrow.strftime("%Y-%m-%d")
        with pytest.raises(ValidationError):
            person.clean()

        # future date range - error
        person.date = f"{today.strftime('%Y-%m-%d')}/{tomorrow.strftime('%Y-%m-%d')}"
        with pytest.raises(ValidationError):
            person.clean()

        # date range with end earlier than start - error
        yesterday = today - datetime.timedelta(days=1)
        person.date = f"{today.strftime('%Y-%m-%d')}/{yesterday.strftime('%Y-%m-%d')}"
        with pytest.raises(ValidationError):
            person.clean()

        # impossible date (invalid day) — form validation error, but not 500
        person.date = "2021-02-30"
        with pytest.raises(ValidationError):
            person.clean()
