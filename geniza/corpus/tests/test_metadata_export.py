import codecs
import csv

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from geniza.corpus.metadata_export import (
    AdminDocumentExporter,
    FragmentExporter,
    PublicDocumentExporter,
    PublicFragmentExporter,
)
from geniza.corpus.models import (
    Collection,
    Dating,
    Document,
    DocumentType,
    Fragment,
    LanguageScript,
)
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


@pytest.mark.django_db
def test_doc_exporter_cli(document, join):
    # get artificial dataset
    exporter = AdminDocumentExporter()

    # csv filename?
    str_time_pref = timezone.now().strftime("%Y%m%dT")
    csv_filename = exporter.csv_filename()
    assert type(csv_filename) == str and csv_filename
    assert csv_filename.startswith(f"geniza-documents-{str_time_pref}")
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
    assert (
        row1["pgpid"] == join.id
    )  # this should be first row -- not document (owing to sorting by ID)

    # correct description in second row?
    row2 = next(iter)
    assert row2.get("description") == document.description


@pytest.mark.django_db
def test_iter_dicts(document):
    # Create all documents
    cul = Collection.objects.create(library="Cambridge", abbrev="CUL")
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21", collection=cul)

    contract = DocumentType.objects.create(name_en="Contract")
    doc = Document.objects.create(
        description="Business contracts with tables",
        doctype=contract,
        notes="Goitein cards",
        needs_review="demerged",
        status=Document.PUBLIC,
    )
    doc.fragments.add(frag)
    doc.tags.add("table")

    arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
    french = LanguageScript.objects.create(language="French", script="Latin")

    doc.languages.add(arabic)
    doc.secondary_languages.add(french)

    marina = Creator.objects.create(last_name_en="Rustow", first_name_en="Marina")
    book = SourceType.objects.create(type="Book")
    source = Source.objects.create(source_type=book)
    source.authors.add(marina)
    footnote = Footnote.objects.create(
        doc_relation=["E"],
        source=source,
        content_type_id=ContentType.objects.get(
            app_label="corpus", model="document"
        ).id,
        object_id=0,
    )
    doc.footnotes.add(footnote)

    doc_qs = Document.objects.all().order_by("id")
    exporter = AdminDocumentExporter(queryset=doc_qs)

    for doc, doc_data in zip(doc_qs, exporter.iter_dicts()):
        # test some properties
        assert doc.id == doc_data.get("pgpid")
        assert doc.shelfmark == doc_data.get("shelfmark")
        if doc.collection:
            assert doc.collection in doc_data.get(
                "collection"
            )  # collection now a set in doc_data

        for fn in doc.footnotes.all():
            assert fn.display() in doc_data.get("scholarship_records")

        # test callables
        assert doc.all_tags() == doc_data.get("tags")

        # test new functions
        assert f"https://example.com/documents/{doc.id}/" == doc_data.get("url")
        assert "Public" == doc_data.get("status")
        assert (
            f"https://example.com/admin/corpus/document/{doc.id}/change/"
            == doc_data.get("url_admin")
        )
        # initial input should be before last modified
        # (document fixture has a log entry, so should have a first input)
        input_date = doc_data.get("initial_entry")
        last_modified = doc_data.get("last_modified")
        if input_date:
            assert input_date < last_modified, (
                "expect input date (%s) to be earlier than last modified (%s) [PGPID %s]"
                % (input_date, last_modified, doc.id)
            )


@pytest.mark.django_db
def test_dating(document):
    # should include dating info in export
    Dating.objects.create(
        document=document,
        display_date="1000 CE example",
        standard_date="1000",
        rationale=Dating.PALEOGRAPHY,
        notes="a note",
    )
    doc_qs = Document.objects.all().order_by("id")
    exporter = AdminDocumentExporter(queryset=doc_qs)
    data_dict = exporter.get_export_data_dict(document)
    assert "1000 CE example" in data_dict["inferred_date_display"]
    assert "1000" in data_dict["inferred_date_standard"]
    assert "a note" in data_dict["inferred_date_notes"]

    # should handle multiple values properly, with separators
    Dating.objects.create(
        document=document,
        display_date="1005-1010",
        standard_date="1005/1010",
        rationale=Dating.PERSON,
        notes="othernote",
    )
    doc_qs = Document.objects.all().order_by("id")
    data_dict = exporter.get_export_data_dict(document)
    assert exporter.sep_within_cells.join(
        [Dating.PALEOGRAPHY_LABEL, Dating.PERSON_LABEL]
    ) in exporter.serialize_value(data_dict["inferred_date_rationale"])


@pytest.mark.django_db
def test_http_export_data_csv(document):
    exporter = AdminDocumentExporter()
    ofn = "test_http_export.csv"
    response = exporter.http_export_data_csv(fn=ofn)
    headers_d = response.headers
    assert headers_d.get("Content-Type") == "text/csv; charset=utf-8"
    assert headers_d.get("Content-Disposition") == f"attachment; filename={ofn}"
    assert response.status_code == 200

    yielded_content = [x.decode() for x in response]
    # first bit of content should be byte order mark)
    assert yielded_content[0] == codecs.BOM_UTF8.decode()

    # remaining rows should be csv
    csv_dictreader = csv.DictReader(yielded_content[1:])

    # next row should be first row of csv dat
    row = next(csv_dictreader)
    # correct data?
    assert row.get("pgpid") == str(document.id)
    # correct header?
    assert set(exporter.csv_fields) == set(row.keys())


@pytest.mark.django_db
def test_public_vs_admin_exporter(document):
    pde = PublicDocumentExporter()
    ade = AdminDocumentExporter()

    pde_d = next(pde.iter_dicts())
    ade_d = next(ade.iter_dicts())

    pde_keys = set(pde_d.keys())
    ade_keys = set(ade_d.keys())

    assert len(pde_keys) < len(ade_keys)
    assert ade_keys - pde_keys == {"notes", "needs_review", "status", "url_admin"}

    # test in the csvs
    pde_iter = pde.iter_csv(pseudo_buffer=True)
    ade_iter = ade.iter_csv(pseudo_buffer=True)

    # skip past encoding char
    next(pde_iter), next(ade_iter)

    # now get headers from csv
    pde_header = next(pde_iter)
    ade_header = next(ade_iter)
    pde_header_keys = set(pde_header.strip().split(","))
    ade_header_keys = set(ade_header.strip().split(","))
    assert ade_header_keys - pde_header_keys == {
        "notes",
        "needs_review",
        "status",
        "url_admin",
    }


@pytest.mark.django_db
def test_fragment_export_data(multifragment):
    data = FragmentExporter().get_export_data_dict(multifragment)
    assert data["shelfmark"] == multifragment.shelfmark
    assert data["pgpids"] == []
    assert data["old_shelfmarks"] == ""
    # fixture is not in a collection
    assert "collection" not in data

    assert data["url"] == multifragment.url
    assert data["iiif_url"] == multifragment.iiif_url
    assert data["created"] == multifragment.created
    assert data["last_modified"] == multifragment.last_modified


@pytest.mark.django_db
def test_fragment_export_data_collection(fragment):
    cul = Collection.objects.create(library="Cambridge", abbrev="CUL")
    fragment.collection = cul
    fragment.save()

    data = FragmentExporter().get_export_data_dict(fragment)
    assert data["collection"] == cul
    assert data["library"] == cul.library
    assert data["library_abbrev"] == cul.lib_abbrev


@pytest.mark.django_db
def test_fragment_export_data_pgpids(fragment, multifragment, document, join):
    # document and join are both on fragment; join is also on multifragment
    data = FragmentExporter().get_export_data_dict(fragment)
    assert document.pk in data["pgpids"]
    assert join.pk in data["pgpids"]

    data = FragmentExporter().get_export_data_dict(multifragment)
    assert data["pgpids"] == [join.pk]


@pytest.mark.django_db
def test_public_fragment_export(fragment, multifragment, document, join):
    # document and join are both on fragment; join is also on multifragment
    qs_frags = [f for f in PublicFragmentExporter().get_queryset()]
    # should include both fragments
    assert fragment in qs_frags
    assert multifragment in qs_frags
    # PublicFragmentExporter should not create duplicate rows for frag
    # associated with multiple documents (fails without distinct())
    assert PublicFragmentExporter().get_queryset().count() == 2
    assert FragmentExporter().get_queryset().count() == 2

    # if we suppress join, then multifragment should no longer be included
    join.status = Document.SUPPRESSED
    join.save()
    qs_frags = [f for f in PublicFragmentExporter().get_queryset()]
    # should include fragment but not multifragment
    assert fragment in qs_frags
    assert multifragment not in qs_frags

    document.delete()
    join.delete()
    # should still be two fragments in the main export
    assert FragmentExporter().get_queryset().count() == 2
    # but none in the public export
    assert PublicFragmentExporter().get_queryset().count() == 0
