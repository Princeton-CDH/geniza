import csv

import pytest
from django.utils import timezone
from django.utils.text import slugify

from geniza.corpus.dates import standard_date_display
from geniza.corpus.models import Dating
from geniza.entities.metadata_export import (
    AdminPersonExporter,
    AdminPlaceExporter,
    PersonRelationsExporter,
    PlaceRelationsExporter,
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
    PlacePlaceRelation,
    PlacePlaceRelationType,
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
        assert obj["source_person"] == str(person)
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
            assert export_data.get("related_people_count") == 2
            assert export_data.get("related_documents_count") == 2
            assert export_data.get("related_events_count") == 2
        elif str(place) == str(mosul):
            assert "Iraq" in export_data.get("notes")
            assert export_data.get("related_people_count") == 1
            assert export_data.get("related_documents_count") == 1
            assert export_data.get("related_events_count") == 0


@pytest.mark.django_db
def test_place_relations_csv(person, document, join):
    # add additional relational data and test single person relations CSV export

    # Create some relationships
    mosul = Place.objects.create(slug="mosul")
    Name.objects.create(content_object=mosul, name="Mosul", primary=True)
    Name.objects.create(content_object=mosul, name="الموصل", primary=False)
    fustat = Place.objects.create(slug="fustat")
    Name.objects.create(content_object=fustat, name="Fusṭāṭ", primary=True)
    aydhab = Place.objects.create(slug="aydhab")
    Name.objects.create(name="ʿAydhāb", content_object=aydhab, primary=True)
    qasr = Place.objects.create(slug="qasr-al-sham")
    Name.objects.create(name="Qaṣr al-Shamʿ", content_object=qasr, primary=True)
    (home_base, _) = PersonPlaceRelationType.objects.get_or_create(name_en="Home base")
    (roots, _) = PersonPlaceRelationType.objects.get_or_create(
        name_en="Family traces roots to"
    )
    PersonPlaceRelation.objects.create(person=person, place=fustat, type=home_base)
    PersonPlaceRelation.objects.create(person=person, place=fustat, type=roots)
    (pdrtype, _) = PersonDocumentRelationType.objects.get_or_create(name="test doc-ps")
    PersonDocumentRelation.objects.create(document=join, person=person, type=pdrtype)
    (dprtype, _) = DocumentPlaceRelationType.objects.get_or_create(name="test doc-pl")
    DocumentPlaceRelation.objects.create(document=document, place=fustat, type=dprtype)
    DocumentPlaceRelation.objects.create(document=join, place=fustat, type=dprtype)
    DocumentPlaceRelation.objects.create(document=document, place=mosul, type=dprtype)
    DocumentPlaceRelation.objects.create(document=join, place=mosul, type=dprtype)
    Dating.objects.create(standard_date="900/980", document=document)
    document.doc_date_standard = "920/1010"
    document.save()
    join.doc_date_standard = "1000/1010"
    join.save()

    (not_same, _) = PlacePlaceRelationType.objects.get_or_create(
        name="Not to be confused with"
    )
    PlacePlaceRelation.objects.create(place_a=fustat, place_b=mosul, type=not_same)
    PlacePlaceRelation.objects.create(place_a=aydhab, place_b=fustat, type=not_same)
    (neighborhood, _) = PlacePlaceRelationType.objects.get_or_create(
        name="Neighborhood",
        converse_name="City",
    )
    PlacePlaceRelation.objects.create(place_a=qasr, place_b=fustat, type=neighborhood)
    evt = Event.objects.create(name="Test event")
    PlaceEventRelation.objects.create(place=fustat, event=evt, notes="test")

    exporter = PlaceRelationsExporter(queryset=Place.objects.filter(pk=fustat.pk))

    for obj in exporter.iter_dicts():
        id = obj["related_object_id"]
        objtype = obj["related_object_type"]
        reltype = obj.get("relationship_type", "")
        assert obj["source_place"] == str(fustat)
        if objtype == "Person":
            assert (
                home_base.name.lower() in reltype.lower()
                and roots.name.lower() in reltype.lower()
            )
            assert ", " in reltype
            assert str(join) in obj["shared_documents"]
        elif objtype == "Place":
            if id == mosul.id:
                assert reltype == not_same.name
                assert str(document) in obj["shared_documents"]
                assert str(join) in obj["shared_documents"]
                assert ", " in obj["shared_documents"]
            elif id == aydhab.id:
                assert reltype == not_same.name
                assert not obj["shared_documents"]
            elif id == qasr.id:
                assert reltype == neighborhood.name
        elif objtype == "Document":
            assert reltype == dprtype.name
            assert obj["related_object_name"] in [str(document), str(join)]
            if id == document.id:
                assert obj["related_object_date"] == standard_date_display("900/1010")
            else:
                assert obj["related_object_date"] == standard_date_display("1000/1010")
        elif objtype == "Event":
            assert "relationship_type" not in obj
            assert obj["related_object_name"] == evt.name
            assert obj["relationship_notes"] == "test"
