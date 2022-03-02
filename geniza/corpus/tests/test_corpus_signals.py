from unittest.mock import patch

import pytest
from parasolr.django.indexing import ModelIndexable

from geniza.corpus.models import (
    Document,
    DocumentSignalHandlers,
    DocumentType,
    Fragment,
)


@pytest.mark.django_db
@patch.object(ModelIndexable, "index_items")
def test_related_save(mock_indexitems, document, join):
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

    # doctype
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save(DocumentType, document.doctype)
    assert mock_indexitems.call_count == 1
    assert document in mock_indexitems.call_args[0][0]
    assert join not in mock_indexitems.call_args[0][0]

    # unhandled model should be ignored, no error
    mock_indexitems.reset_mock()
    DocumentSignalHandlers.related_save(Document, document)
    mock_indexitems.assert_not_called()


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
