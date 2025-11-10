from unittest.mock import patch

import pytest
from parasolr.django.indexing import ModelIndexable
from taggit.models import Tag

from geniza.corpus.models import (
    Document,
    DocumentSignalHandlers,
    DocumentType,
    Fragment,
)


@pytest.mark.django_db
@patch.object(ModelIndexable, "index_items")
def test_related_save(mock_indexitems, document, join, footnote, annotation):
    # unsaved fragment should be ignored
    frag = Fragment(shelfmark="T-S 123")

    # unsaved - ignore
    DocumentSignalHandlers.related_save(Fragment, frag)
    mock_indexitems.assert_not_called()
    # raw - ignore
    DocumentSignalHandlers.related_save(Fragment, frag, raw=True)
    mock_indexitems.assert_not_called()
    # saved but no associated documents
    frag.save()
    DocumentSignalHandlers.related_save(Fragment, frag)
    mock_indexitems.assert_not_called()

    # fragment associated with a document
    DocumentSignalHandlers.related_save(Fragment, document.fragments.first())
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]
    assert join in mock_indexitems.call_args[0][0]

    # footnote
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save(DocumentType, document.footnotes.first())
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]

    # source
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save(DocumentType, document.footnotes.first().source)
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]

    # creator
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save(
        DocumentType, document.footnotes.first().source.authorship_set.first().creator
    )
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]

    # annotation
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save(
        DocumentType,
        document.footnotes.filter(annotation__isnull=False)
        .first()
        .annotation_set.first(),
    )
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]

    # unhandled model should be ignored, no error
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save(Document, document)
    mock_indexitems.assert_not_called()


@pytest.mark.django_db
@patch.object(ModelIndexable, "index_items")
def test_related_save_doctype(mock_indexitems, document, join):
    # doctype: should only update when update_fields not passed, or name_en or display_label_en updated
    DocumentSignalHandlers.related_save_doctype(DocumentType, document.doctype)
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]
    assert join not in mock_indexitems.call_args[0][0]
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save_doctype(
        DocumentType, document.doctype, update_fields=["name_en"]
    )
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]
    assert join not in mock_indexitems.call_args[0][0]
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save_doctype(
        DocumentType, document.doctype, update_fields=["display_label_en"]
    )
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]
    assert join not in mock_indexitems.call_args[0][0]

    # should not update on other language names/labels changing
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save_doctype(
        DocumentType, document.doctype, update_fields=["name_he"]
    )
    assert mock_indexitems.call_count == 0


@pytest.mark.django_db
@patch.object(ModelIndexable, "index_items")
def test_related_delete(mock_indexitems, document, join):
    # delegates to same method as save, just check a few cases

    # fragment associated with a document
    DocumentSignalHandlers.related_delete(Fragment, document.fragments.first())
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]
    assert join in mock_indexitems.call_args[0][0]

    # doctype
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_delete(DocumentType, document.doctype)
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]
    assert join not in mock_indexitems.call_args[0][0]


@pytest.mark.django_db
def test_unidecode_tags():
    # pre_save signal should strip diacritics from tag and convert to ASCII
    tag = Tag.objects.create(name="mu'ālim", slug="mualim")
    assert tag.name == "mu'alim"


@pytest.mark.django_db
@patch.object(ModelIndexable, "index_items")
def test_tagged_item_change(mock_indexitems, document):
    tag_count = document.tags.count()
    tag = Tag.objects.create(name="mu'ālim", slug="mualim")
    tag2 = Tag.objects.create(name="tag2", slug="tag2")
    # should reindex document with the updated set of tags on save
    document.tags.add(tag)
    document.tags.add(tag2)
    document.save()
    # should be called at least once for the document post-save & once for the tags M2M change
    assert mock_indexitems.call_count >= 2
    # most recent call should have the full updated set of tags
    assert mock_indexitems.call_args.args[0][0].tags.count() == tag_count + 2
