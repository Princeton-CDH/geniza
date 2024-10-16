import csv

import pytest
from django.utils import timezone

from geniza.entities.metadata_export import AdminPersonExporter
from geniza.entities.models import (
    Name,
    Person,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    Place,
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
def test_iter_dicts(person, person_diacritic, person_multiname, document, join):
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
