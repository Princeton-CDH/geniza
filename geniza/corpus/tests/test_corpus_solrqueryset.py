from unittest.mock import patch

from parasolr.django import AliasedSolrQuerySet
from piffle.image import IIIFImageClient

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
            dqs.keyword_search("pgpid:950 shelfmark:ena tag:state")
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                keyword_query="pgpid_i:950 shelfmark_t:ena tags_ss_lower:state"
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
