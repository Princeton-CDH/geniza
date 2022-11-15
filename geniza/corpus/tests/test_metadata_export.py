import csv
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models.query import EmptyQuerySet
from django.forms import modelform_factory
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from pytest_django.asserts import assertContains, assertNotContains

from geniza.corpus.admin import (
    DocumentAdmin,
    DocumentForm,
    FragmentAdmin,
    FragmentTextBlockInline,
    HasTranscriptionListFilter,
    LanguageScriptAdmin,
)
from geniza.corpus.metadata_export import (
    AdminDocumentExporter,
    FragmentExporter,
    PublicDocumentExporter,
)
from geniza.corpus.models import (
    Collection,
    Document,
    DocumentType,
    Fragment,
    LanguageScript,
    TextBlock,
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
        assert doc.collection == doc_data.get("collection")

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
def test_http_export_data_csv(document):
    exporter = AdminDocumentExporter()
    ofn = "test_http_export.csv"
    response = exporter.http_export_data_csv(fn=ofn)
    headers_d = response.headers
    assert headers_d.get("Content-Type") == "text/csv; charset=utf-8"
    assert headers_d.get("Content-Disposition") == f"attachment; filename={ofn}"

    assert response.status_code == 200

    def iter_http_response_lines_str(response):
        for x in response:
            yield x.decode()

    row = next(csv.DictReader(iter_http_response_lines_str(response)))

    # correct row?
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
    assert ade_keys - pde_keys
    assert ade_keys - pde_keys == {"notes", "needs_review", "status", "url_admin"}


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
    # document and join are both on fragment; fragment is also on multifragment
    data = FragmentExporter().get_export_data_dict(fragment)
    assert document.pk in data["pgpids"]
    assert join.pk in data["pgpids"]

    data = FragmentExporter().get_export_data_dict(multifragment)
    assert data["pgpids"] == [join.pk]
