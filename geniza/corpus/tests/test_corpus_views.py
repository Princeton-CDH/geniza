import pytest
from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock
from geniza.footnotes.models import Footnote, Source, SourceType, Creator
from pytest_django.asserts import assertContains
from geniza.corpus.views import parse_edition_string, tabulate_queryset
from django.contrib.contenttypes.models import ContentType


class TestDocumentDetailView:
    def test_get_queryset(self, db, client):
        # Ensure page works normally when not suppressed
        doc = Document.objects.create()
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 200
        assertContains(response, "Shelfmark")

        # Test that when status isn't public, it is suppressed
        doc = Document.objects.create(status=Document.SUPPRESSED)
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 404


@pytest.mark.django_db
def test_tabulate_queryset():
    legal_doc = DocumentType.objects.create(name="Legal")
    doc = Document.objects.create(id=36, doctype=legal_doc)
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
    TextBlock.objects.create(document=doc, fragment=frag, side="r")
    doc.fragments.add(frag)
    doc.tags.add("marriage")

    table_iter = tabulate_queryset(Document.objects.all())
    row = next(table_iter)
    print(row)

    assert "T-S 8J22.21" in row
    assert "marriage" in row
    assert "recto" in row

    # NOTE: strings are not parsed until after being fed into the csv plugin
    assert legal_doc in row
    assert 36 in row


@pytest.mark.django_db
def test_parse_edition_string():
    # Expected behavior:
    # Ed. [fn].
    # Ed. [fn]; also ed. [fn].
    # Ed. [fn]; also ed. [fn]; also trans. [fn].
    # Ed. [fn] [url]; also ed. [fn]; also trans. [fn].

    doc = Document.objects.create()
    assert parse_edition_string(doc.editions()) == ""

    marina = Creator.objects.create(last_name="Rustow", first_name="Marina")
    book = SourceType.objects.create(type="Book")
    source = Source.objects.create(source_type=book)
    source.authors.add(marina)
    fn = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source,
        content_type_id=ContentType.objects.get(model="document").id,
        object_id=0,
    )
    doc.footnotes.add(fn)

    edition_str = parse_edition_string(doc.editions())
    assert edition_str == f"Ed. {fn.display()}"

    source2 = Source.objects.create(title="Arabic dictionary", source_type=book)
    fn2 = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source2,
        content_type_id=ContentType.objects.get(model="document").id,
        object_id=0,
    )
    doc.footnotes.add(fn2)
    edition_str = parse_edition_string(doc.editions())
    assert edition_str == f"Ed. Arabic dictionary; also ed. Rustow."

    source3 = Source.objects.create(title="Geniza Encyclopedia", source_type=book)
    fn_trans = Footnote.objects.create(
        doc_relation=[Footnote.EDITION, Footnote.TRANSLATION],
        source=source3,
        content_type_id=ContentType.objects.get(model="document").id,
        object_id=0,
    )
    doc.footnotes.add(fn_trans)
    edition_str = parse_edition_string(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also trans. Geniza Encyclopedia; also ed. Rustow."
    )

    fn.url = "example.com"
    fn.save()
    edition_str = parse_edition_string(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also trans. Geniza Encyclopedia; also ed. Rustow example.com."
    )
