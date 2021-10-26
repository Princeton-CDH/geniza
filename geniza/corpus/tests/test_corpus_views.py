from time import sleep
from unittest.mock import Mock, patch

import pytest
from django.db.models.fields import related
from django.http.response import Http404
from django.urls import reverse
from django.utils.text import Truncator
from parasolr.django import SolrClient
from pytest_django.asserts import assertContains

from geniza.common.utils import absolutize_url
from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.views import (
    DocumentDetailView,
    DocumentScholarshipView,
    DocumentSearchView,
    old_pgp_edition,
    old_pgp_tabulate_data,
    pgp_metadata_for_old_site,
)
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


class TestDocumentDetailView:
    def test_page_title(self, document, client):
        """should use doc title as detail view meta title"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        assert response.context["page_title"] == document.title

    def test_page_description(self, document, client):
        """should use truncated doc description as detail view meta description"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        assert response.context["page_description"] == Truncator(
            document.description
        ).words(20)

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

    def test_permalink(self, document, client):
        """should contain permalink generated from absolutize_url"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        permalink = absolutize_url(document.get_absolute_url())
        assertContains(response, f'<link rel="canonical" href="{permalink}"')

    def test_past_id_mixin(self, db, client):
        """should redirect from 404 to new pgpid when an old_pgpid is matched"""
        response_404 = client.get(reverse("corpus:document", args=(2,)))
        assert response_404.status_code == 404
        doc = Document.objects.create(id=1, old_pgpids=[2])
        response_301 = client.get(reverse("corpus:document", args=(2,)))
        assert response_301.status_code == 301
        assert response_301.url == doc.permalink

        # Test when pgpid not first in the list
        response_404_notfirst = client.get(reverse("corpus:document", args=(71,)))
        assert response_404_notfirst.status_code == 404
        doc.old_pgpids = [5, 6, 71]
        doc.save()
        response_301_notfirst = client.get(reverse("corpus:document", args=(71,)))
        assert response_301_notfirst.status_code == 301
        assert response_301_notfirst.url == doc.permalink

        # Test partial matching pgpid
        response_404_partialmatch = client.get(reverse("corpus:document", args=(7,)))
        assert response_404_partialmatch.status_code == 404

    def test_get_absolute_url(self, document):
        """should return doc permalink"""
        doc_detail_view = DocumentDetailView()
        doc_detail_view.object = document
        doc_detail_view.kwargs = {"pk": document.pk}
        assert doc_detail_view.get_absolute_url() == document.permalink


@pytest.mark.django_db
def test_old_pgp_tabulate_data():
    legal_doc = DocumentType.objects.create(name="Legal")
    doc = Document.objects.create(id=36, doctype=legal_doc)
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
    TextBlock.objects.create(document=doc, fragment=frag, side="r")
    doc.fragments.add(frag)
    doc.tags.add("marriage")

    table_iter = old_pgp_tabulate_data(Document.objects.all())
    row = next(table_iter)

    assert "T-S 8J22.21" in row
    assert "#marriage" in row
    assert "recto" in row
    # should not error on document with no old pgpids

    # NOTE: strings are not parsed until after being fed into the csv plugin
    assert legal_doc in row
    assert 36 in row

    doc.old_pgpids = [12345, 67890]
    doc.save()
    table_iter = old_pgp_tabulate_data(Document.objects.all())
    row = next(table_iter)
    assert "12345;67890" in row


@pytest.mark.django_db
def test_old_pgp_edition():
    # Expected behavior:
    # Ed. [fn].
    # Ed. [fn]; also ed. [fn].
    # Ed. [fn]; also ed. [fn]; also trans. [fn].
    # Ed. [fn] [url]; also ed. [fn]; also trans. [fn].

    doc = Document.objects.create()
    assert old_pgp_edition(doc.editions()) == ""

    marina = Creator.objects.create(last_name="Rustow", first_name="Marina")
    book = SourceType.objects.create(type="Book")
    source = Source.objects.create(source_type=book)
    source.authors.add(marina)
    fn = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source,
        content_object=doc,
    )
    doc.footnotes.add(fn)

    edition_str = old_pgp_edition(doc.editions())
    assert edition_str == f"Ed. {fn.display()}"

    source2 = Source.objects.create(title="Arabic dictionary", source_type=book)
    fn2 = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source2,
        content_object=doc,
    )
    doc.footnotes.add(fn2)
    edition_str = old_pgp_edition(doc.editions())
    assert edition_str == f"Ed. Arabic dictionary; also ed. Marina Rustow."

    source3 = Source.objects.create(title="Geniza Encyclopedia", source_type=book)
    fn_trans = Footnote.objects.create(
        doc_relation=[Footnote.EDITION, Footnote.TRANSLATION],
        source=source3,
        content_object=doc,
    )
    doc.footnotes.add(fn_trans)
    edition_str = old_pgp_edition(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also ed. and trans. Geniza Encyclopedia; also ed. Marina Rustow."
    )

    fn.url = "example.com"
    fn.save()
    edition_str = old_pgp_edition(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also ed. and trans. Geniza Encyclopedia; also ed. Marina Rustow example.com."
    )


@pytest.mark.django_db
def test_pgp_metadata_for_old_site():
    legal_doc = DocumentType.objects.create(name="Legal")
    doc = Document.objects.create(id=36, doctype=legal_doc)
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
    TextBlock.objects.create(document=doc, fragment=frag, side="r")
    doc.fragments.add(frag)
    doc.tags.add("marriage")

    doc2 = Document.objects.create(status=Document.SUPPRESSED)

    response = pgp_metadata_for_old_site(Mock())
    assert response.status_code == 200

    streaming_content = response.streaming_content
    header = next(streaming_content)
    row1 = next(streaming_content)

    # Ensure no suppressed documents are published
    with pytest.raises(StopIteration):
        row2 = next(streaming_content)

    # Ensure objects have been correctly parsed as strings
    assert b"36" in row1
    assert b"Legal" in row1


class TestDocumentSearchView:
    def test_get_form_kwargs(self):
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # no params
        docsearch_view.request.GET = {}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {},
            "prefix": None,
            "data": {},
        }

        # keyword search param
        docsearch_view.request.GET = {"query": "contract"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {},
            "prefix": None,
            "data": {"query": "contract", "sort": "relevance"},
        }

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_get_queryset(self, mock_solr_queryset):
        with patch(
            "geniza.corpus.views.DocumentSolrQuerySet",
            new=self.mock_solr_queryset(DocumentSolrQuerySet),
        ) as mock_queryset_cls:

            docsearch_view = DocumentSearchView()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {"query": "six apartments"}
            qs = docsearch_view.get_queryset()

            mock_queryset_cls.assert_called_with()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_called_with("six apartments")
            # NOTE: keyword search not in parasolr list for mock solr queryset
            mock_sqs.keyword_search.return_value.also.assert_called_with("score")

    def test_get_context_data(self, rf):
        docsearch_view = DocumentSearchView()
        docsearch_view.request = rf.get("/documents/")
        docsearch_view.queryset = Mock()
        docsearch_view.queryset.count.return_value = 22
        docsearch_view.object_list = docsearch_view.queryset

        context_data = docsearch_view.get_context_data()
        assert context_data["total"] == 22

    def test_shelfmark_boost(self, empty_solr, document, multifragment):
        # integration test for shelfmark field boosting
        # in solr configuration
        # - using empty solr fixture to ensure solr is empty when this test starts

        # create a second document with a different shelfmark
        # that references the shelfmark of the first in the description
        related_doc = Document.objects.create(
            description="See also %s" % document.shelfmark
        )
        TextBlock.objects.create(document=related_doc, fragment=multifragment)

        # third document with similar shelfmark
        frag = Fragment.objects.create(
            shelfmark="CUL Add.300",  # fixture has shelfmark CUL Add.2586
        )
        neighbor_doc = Document.objects.create()
        TextBlock.objects.create(document=neighbor_doc, fragment=frag)
        # ensure solr index is updated with all three test documents
        SolrClient().update.index(
            [
                document.index_data(),
                neighbor_doc.index_data(),
                related_doc.index_data(),
            ],
            commit=True,
        )

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # assuming relevance sort is default; update if that changes
        docsearch_view.request.GET = {"query": document.shelfmark}
        qs = docsearch_view.get_queryset()
        # should return all three documents
        assert qs.count() == 3
        # document with exact match on shelfmark should be returned first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with matching shelfmark returned first"
        # document with full shelfmark should in description should be second
        assert (
            qs[1]["pgpid"] == related_doc.id
        ), "document with shelfmark in description returned second"
        # (document with similar shelfmark is third)


class TestDocumentScholarshipView:
    def test_page_title(self, document, client, source):
        """should incorporate doc title into scholarship page title"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=(document.id,))
        )
        assert response.context["page_title"] == f"Scholarship on {document.title}"

    def test_page_description(self, document, client, source):
        """should use number of scholarship records as scholarship page description"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=(document.id,))
        )
        assert (
            response.context["page_description"]
            == f"1 scholarship record for {document.title}"
        )

    def test_get_queryset(self, client, document, source):
        # no footnotes; should 404
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.status_code == 404

        # add a footnote; should return document in context
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.context["document"] == document

        # suppress document; should 404 again
        document.status = Document.SUPPRESSED
        document.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.status_code == 404

    # def test_get_absolute_url(self, db, client):

    def test_past_id_mixin(self, db, client, source):
        """should redirect from 404 to new pgpid when an old_pgpid is matched"""
        response_404 = client.get(reverse("corpus:document-scholarship", args=[2]))
        assert response_404.status_code == 404
        doc = Document.objects.create(id=1, old_pgpids=[2])
        Footnote.objects.create(content_object=doc, source=source)
        response_301 = client.get(reverse("corpus:document-scholarship", args=[2]))
        assert response_301.status_code == 301
        assert response_301.url == f"{doc.permalink}scholarship/"

    def test_get_absolute_url(self, document, source):
        """should return scholarship permalink"""
        Footnote.objects.create(content_object=document, source=source)
        doc_detail_view = DocumentScholarshipView()
        doc_detail_view.object = document
        doc_detail_view.kwargs = {"pk": document.pk}
        assert doc_detail_view.get_absolute_url() == f"{document.permalink}scholarship/"
