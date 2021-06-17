from unittest.mock import patch

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

            # ignore + when searching on joins
            dqs.admin_search("CUL Or.1080 3.41 + T-S 13J16.20 + T-S 13J8.14")
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                doc_query="CUL Or.1080 3.41 T-S 13J16.20 T-S 13J8.14"
            )
