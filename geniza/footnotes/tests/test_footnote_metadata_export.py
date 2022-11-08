import pytest

from geniza.footnotes.metadata_export import SourceExporter


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
    assert (
        data["admin_url"]
        == f"https://example.com/admin/footnotes/source/{source.id}/change/"
    )
