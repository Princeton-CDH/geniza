from unittest.mock import patch

from parasolr.django import AliasedSolrQuerySet, SolrClient
from piffle.image import IIIFImageClient

from geniza.corpus.models import Document, DocumentType, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet


class TestDocumentSolrQuerySet:
    def test_admin_search(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            dqs.admin_search("deed of sale")
            mocksearch.assert_called_with(dqs.admin_doc_qf)
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                doc_query="deed of sale"
            )

    def test_admin_search_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            # ignore + when searching on joins
            dqs.admin_search("CUL Or.1080 3.41 + T-S 13J16.20 + T-S 13J8.14")
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                doc_query="CUL Or.1080 3.41 T-S 13J16.20 T-S 13J8.14"
            )

    def test_keyword_search_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            # ignore + when searching on joins
            dqs.keyword_search("CUL Or.1080 3.41 + T-S 13J16.20 + T-S 13J8.14")
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                keyword_query="CUL Or.1080 3.41 T-S 13J16.20 T-S 13J8.14"
            )

    def test_keyword_search_field_aliases(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            dqs.keyword_search("pgpid:950 old_pgpid:931 tag:state")
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                keyword_query="pgpid_i:950 old_pgpids_is:931 tags_ss_lower:state"
            )

    def test_keyword_search_field_alias_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            dqs.keyword_search("shelfmark:ena")
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                keyword_query="%sena" % dqs.shelfmark_qf
            )

    def test_get_result_document(self):
        dqs = DocumentSolrQuerySet()
        mock_doc = {
            "iiif_images": [
                "http://example.co/iiif/ts-1/00001",
                "http://example.co/iiif/ts-1/00002",
            ],
            "iiif_labels": ["1r", "1v"],
        }
        with patch.object(
            AliasedSolrQuerySet, "get_result_document", return_value=mock_doc
        ):
            result_doc = dqs.get_result_document(mock_doc)
            result_imgs = result_doc["iiif_images"]
            # should produce a list of 2 tuples, each containing a IIIFImageClient and label, from above dict
            assert len(result_imgs) == 2
            assert isinstance(result_imgs[0][0], IIIFImageClient)
            assert (
                result_imgs[0][0].info()
                == "http://example.co/iiif/ts-1/00001/info.json"
            )
            assert result_imgs[0][1] == "1r"

    def test_search_term_cleanup__arabic_to_ja(self):
        dqs = DocumentSolrQuerySet()
        # confirm arabic to judaeo-arabic runs here
        dqs._search_term_cleanup("دينار") == "(دينار|דיהאר)"

    def test_related_to(self, document, join, fragment, empty_solr):
        """should give filtered result: public documents with any shared shelfmarks"""

        # create suppressed document on the same fragment as document fixture
        suppressed = Document.objects.create(
            doctype=DocumentType.objects.get_or_create(name_en="Legal")[0],
            status=Document.SUPPRESSED,
        )
        TextBlock.objects.create(document=suppressed, fragment=fragment)
        Document.index_items([document, join, suppressed])
        SolrClient().update.index([], commit=True)

        dqs = DocumentSolrQuerySet()
        related_docs = dqs.related_to(document)

        # should exclude related but suppressed documents
        assert related_docs.filter(pgpid=suppressed.id).count() == 0

        # should exclude self
        assert related_docs.filter(pgpid=document.id).count() == 0

        # should include related
        assert related_docs.filter(pgpid=join.id).count() == 1
