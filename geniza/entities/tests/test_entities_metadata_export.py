import csv

import pytest
from django.utils import timezone
from django.utils.text import slugify

from geniza.entities.metadata_export import (
    AdminPersonExporter,
    AdminPlaceExporter,
    PersonRelationsExporter,
)
from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Event,
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonEventRelation,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    Place,
    PlaceEventRelation,
)

# adapted from corpus/tests/test_metadata_export.py


@pytest.mark.django_db
def test_person_exporter_cli(person, person_multiname):
    # get artificial dataset
    exporter = AdminPersonExporter()

    # csv filename?
    str_time_pref = timezone.now().strftime("%Y%m%dT")
    csv_filename = exporter.csv_filename()
    assert type(csv_filename) == str and csv_filename
    assert csv_filename.startswith(f"geniza-People-{str_time_pref}")
    assert csv_filename.endswith(".csv")

    # correct number of rows?

    ## ...in queryset?
    queryset = exporter.get_queryset()
    assert len(queryset) == 2

    ## ...in data?
    rows = list(exporter.iter_dicts())
    assert len(rows) == 2

    ## ...in csv output?
    testfn = "test_metadata_export.csv"
    exporter.write_export_data_csv(fn=testfn)
    with open(testfn) as f:
        csv_reader = csv.DictReader(f)
        assert len(list(csv_reader)) == 2  # 2 rows of data (as defined in conftest.py)

    iter = exporter.iter_dicts()
    row1 = next(iter)
    assert row1.get("name") == str(
        person
    )  # this should be first row -- not person_multiname (owing to sorting by slug)

    row2 = next(iter)
    assert row2.get("name") == str(person_multiname)


@pytest.mark.django_db
def test_person_iter_dicts(person, person_diacritic, person_multiname, document, join):
    # Create some relationships
    person.has_page = True
    person.save()

    mosul = Place.objects.create(slug="mosul")
    Name.objects.create(content_object=mosul, name="Mosul", primary=True)
    Name.objects.create(content_object=mosul, name="الموصل", primary=False)
    fustat = Place.objects.create(slug="fustat")
    Name.objects.create(content_object=fustat, name="Fusṭāṭ", primary=True)
    (home_base, _) = PersonPlaceRelationType.objects.get_or_create(name_en="Home base")
    (roots, _) = PersonPlaceRelationType.objects.get_or_create(
        name_en="Family traces roots to"
    )
    PersonPlaceRelation.objects.create(person=person, place=mosul, type=home_base)
    PersonPlaceRelation.objects.create(person=person_diacritic, place=mosul, type=roots)
    PersonPlaceRelation.objects.create(
        person=person_diacritic, place=fustat, type=roots
    )

    person.documents.add(document)
    person.documents.add(join)
    person_multiname.documents.add(document)

    (partner, _) = PersonPersonRelationType.objects.get_or_create(
        name_en="Partner", category=PersonPersonRelationType.BUSINESS
    )
    PersonPersonRelation.objects.create(
        from_person=person, to_person=person_diacritic, type=partner
    )

    pqs = Person.objects.all().order_by("slug")
    exporter = AdminPersonExporter(queryset=pqs)

    for pers, export_data in zip(pqs, exporter.iter_dicts()):
        # test some properties
        assert str(pers) == export_data.get("name")
        assert (
            f"https://example.com/admin/entities/person/{pers.id}/change/"
            == export_data.get("url_admin")
        )
        for n in pers.names.non_primary():
            assert str(n) in export_data.get("name_variants")
        if pers.get_absolute_url():
            assert pers.permalink == export_data.get("url")
        if str(pers) == str(person):
            assert export_data.get("related_people_count") == 1
            assert export_data.get("related_documents_count") == 2
            assert "Mosul" in export_data.get("home_base")
        elif str(pers) == str(person_multiname):
            assert export_data.get("related_people_count") == 0
            assert export_data.get("related_documents_count") == 1
        elif str(pers) == str(person_diacritic):
            assert export_data.get("related_people_count") == 1
            assert export_data.get("related_documents_count") == 0
            # should be in alphabetical order
            assert "Fusṭāṭ, Mosul" in export_data.get("family_traces_roots_to")


@pytest.mark.django_db
def test_person_relations_exporter_cli(person):
    # get artificial dataset
    exporter = PersonRelationsExporter(queryset=Person.objects.filter(pk=person.pk))

    # csv filename?
    str_time_pref = timezone.now().strftime("%Y%m%dT")
    csv_filename = exporter.csv_filename()
    assert type(csv_filename) == str and csv_filename
    assert csv_filename.startswith(
        f"geniza-{slugify(str(person))}-person-relations-{str_time_pref}"
    )
    assert csv_filename.endswith(".csv")


@pytest.mark.django_db
def test_person_relations_csv(
    person, person_diacritic, person_multiname, document, join
):
    # add additional relational data and test single person relations CSV export

    # Create some relationships
    mosul = Place.objects.create(slug="mosul")
    Name.objects.create(content_object=mosul, name="Mosul", primary=True)
    Name.objects.create(content_object=mosul, name="الموصل", primary=False)
    fustat = Place.objects.create(slug="fustat")
    Name.objects.create(content_object=fustat, name="Fusṭāṭ", primary=True)
    (home_base, _) = PersonPlaceRelationType.objects.get_or_create(name_en="Home base")
    (roots, _) = PersonPlaceRelationType.objects.get_or_create(
        name_en="Family traces roots to"
    )
    PersonPlaceRelation.objects.create(person=person, place=mosul, type=home_base)
    PersonPlaceRelation.objects.create(person=person, place=fustat, type=roots)
    (pdrtype, _) = PersonDocumentRelationType.objects.get_or_create(name="test")
    PersonDocumentRelation.objects.create(
        document=document, person=person, type=pdrtype
    )
    PersonDocumentRelation.objects.create(document=join, person=person, type=pdrtype)
    PersonDocumentRelation.objects.create(
        document=document, person=person_diacritic, type=pdrtype
    )
    PersonDocumentRelation.objects.create(
        document=join, person=person_diacritic, type=pdrtype
    )
    (partner, _) = PersonPersonRelationType.objects.get_or_create(
        name_en="Partner", category=PersonPersonRelationType.BUSINESS
    )
    (cousin, _) = PersonPersonRelationType.objects.get_or_create(
        name_en="Maternal cousin",
        converse_name_en="Cousin",
        category=PersonPersonRelationType.EXTENDED_FAMILY,
    )
    PersonPersonRelation.objects.create(
        from_person=person, to_person=person_diacritic, type=partner
    )
    PersonPersonRelation.objects.create(
        from_person=person, to_person=person_diacritic, type=cousin
    )
    PersonPersonRelation.objects.create(
        from_person=person_multiname, to_person=person, type=cousin
    )
    evt = Event.objects.create(name="Test event")
    PersonEventRelation.objects.create(person=person, event=evt)

    exporter = PersonRelationsExporter(queryset=Person.objects.filter(pk=person.pk))

    for obj in exporter.iter_dicts():
        id = obj["related_object_id"]
        objtype = obj["related_object_type"]
        reltype = obj.get("relationship_type", "")
        if objtype == "Person":
            if id == person_diacritic.id:
                assert reltype == "Maternal cousin, partner"
                assert str(document) in obj["shared_documents"]
                assert ", " in obj["shared_documents"]
            elif id == person_multiname.id:
                assert reltype == cousin.converse_name
        elif objtype == "Place":
            if id == mosul.id:
                assert reltype == home_base.name
            elif id == fustat.id:
                assert reltype == roots.name
        elif objtype == "Document":
            assert reltype == pdrtype.name
            assert obj["related_object_name"] in [str(document), str(join)]
        elif objtype == "Event":
            assert "relationship_type" not in obj
            assert obj["related_object_name"] == evt.name


@pytest.mark.django_db
def test_place_iter_dicts(person, person_multiname, document, join):
    # create some places
    mosul = Place.objects.create(slug="mosul", notes="A city in Iraq")
    Name.objects.create(content_object=mosul, name="Mosul", primary=True)
    Name.objects.create(content_object=mosul, name="الموصل", primary=False)
    fustat = Place.objects.create(slug="fustat")
    Name.objects.create(content_object=fustat, name="Fusṭāṭ", primary=True)

    # create some relationships
    (home_base, _) = PersonPlaceRelationType.objects.get_or_create(name_en="Home base")
    (roots, _) = PersonPlaceRelationType.objects.get_or_create(
        name_en="Family traces roots to"
    )
    PersonPlaceRelation.objects.create(person=person, place=mosul, type=home_base)
    PersonPlaceRelation.objects.create(person=person, place=fustat, type=roots)
    PersonPlaceRelation.objects.create(
        person=person_multiname, place=fustat, type=roots
    )
    (dest, _) = DocumentPlaceRelationType.objects.get_or_create(name="Destination")
    (ment, _) = DocumentPlaceRelationType.objects.get_or_create(
        name="Possibly mentioned"
    )
    DocumentPlaceRelation.objects.create(place=fustat, type=dest, document=document)
    DocumentPlaceRelation.objects.create(place=fustat, type=dest, document=join)
    DocumentPlaceRelation.objects.create(place=mosul, type=ment, document=join)
    evt1 = Event.objects.create(name="Somebody went to Fustat", standard_date="1000")
    PlaceEventRelation.objects.create(place=fustat, event=evt1)
    evt2 = Event.objects.create(
        name="Somebody else went to Fustat", standard_date="1010"
    )
    PlaceEventRelation.objects.create(place=fustat, event=evt2)

    # test the export dict
    pqs = Place.objects.all().order_by("slug")
    exporter = AdminPlaceExporter(queryset=pqs)

    for place, export_data in zip(pqs, exporter.iter_dicts()):
        assert str(place) == export_data.get("name")
        for n in place.names.non_primary():
            assert str(n) in export_data.get("name_variants")
        assert (
            f"https://example.com/admin/entities/place/{place.id}/change/"
            == export_data.get("url_admin")
        )
        assert place.permalink == export_data.get("url")
        if str(place) == str(fustat):
            # should snake-case each relation type name and append related object
            # type (i.e. _people, _documents)
            assert str(person) in export_data.get("family_traces_roots_to_people")
            assert str(person_multiname) in export_data.get(
                "family_traces_roots_to_people"
            )
            assert str(document) in export_data.get("destination_documents")
            assert str(join) in export_data.get("destination_documents")
            assert "Somebody went" in export_data.get("events")
            assert "Somebody else went" in export_data.get("events")
        elif str(place) == str(mosul):
            assert "Iraq" in export_data.get("notes")
            assert str(person) in export_data.get("home_base_people")
            assert str(join) in export_data.get("possibly_mentioned_documents")
