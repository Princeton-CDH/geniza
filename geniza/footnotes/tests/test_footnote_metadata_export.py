import pytest

from geniza.footnotes.metadata_export import (
    AdminFootnoteExporter,
    AdminSourceExporter,
    FootnoteExporter,
    SourceExporter,
)
from geniza.footnotes.models import Footnote, SourceLanguage


@pytest.mark.django_db
def test_source_export_queryset(source, article):
    qs = SourceExporter().get_queryset()
    # footnote count annotation should be present
    assert hasattr(qs.first(), "footnote__count")


@pytest.mark.django_db
def test_source_export_data(source):
    # add a url to the fixture source
    source.url = "http://example.com"
    source.save()

    src_exporter = SourceExporter()
    # get source via exporter queryset for footnote count annotation
    source_obj = src_exporter.get_queryset().get(pk=source.id)

    data = src_exporter.get_export_data_dict(source_obj)
    assert data["source_type"] == source.source_type
    assert str(source.authorship_set.first().creator) in data["authors"]
    assert data["title"] == source.title
    assert data["journal_book"] == source.journal
    assert data["year"] == source.year
    assert data["url"] == source.url
    assert source.languages.first().name in data["languages"]
    # no footnotes in this fixture
    assert data["num_footnotes"] == 0
    assert "url_admin" not in data

    # should not include Unspecified language
    source.languages.clear()
    source.languages.add(SourceLanguage.objects.get(code="zxx"))
    source_obj = src_exporter.get_queryset().get(pk=source.id)
    data = src_exporter.get_export_data_dict(source_obj)
    assert not data["languages"]

    # should include citation
    assert data["citation"] == str(source)


@pytest.mark.django_db
def test_admin_source_export_data(source):
    admin_src_exporter = AdminSourceExporter()
    # get source via exporter queryset for footnote count annotation
    source_obj = admin_src_exporter.get_queryset().get(pk=source.id)
    data = admin_src_exporter.get_export_data_dict(source_obj)
    assert (
        data["url_admin"]
        == f"https://example.com/admin/footnotes/source/{source.id}/change/"
    )


@pytest.mark.django_db
def test_footnote_export_data(source, document):
    footnote = Footnote(source=source, location="p. 11", notes="extra details")
    footnote.content_object = document
    footnote.save()

    fn_exporter = FootnoteExporter()
    data = fn_exporter.get_export_data_dict(footnote)
    assert data["document"] == document
    assert data["document_id"] == document.pk
    assert data["source"] == source
    assert data["location"] == footnote.location
    assert data["doc_relation"] == footnote.get_doc_relation_list()
    assert data["notes"] == footnote.notes
    assert "url_admin" not in data
    # empty content should not serialize to None
    assert data["content"] == ""


@pytest.mark.django_db
def test_admin_footnote_export_data(source, document):
    footnote = Footnote(source=source)
    footnote.content_object = document
    footnote.save()

    admin_fn_exporter = AdminFootnoteExporter()
    data = admin_fn_exporter.get_export_data_dict(footnote)
    assert (
        data["url_admin"]
        == f"https://example.com/admin/footnotes/footnote/{footnote.id}/change/"
    )
