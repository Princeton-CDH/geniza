from unittest.mock import patch

from parasolr.django import AliasedSolrQuerySet, SolrClient
from piffle.image import IIIFImageClient

from geniza.corpus.models import Document, DocumentType, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet, clean_html


class TestDocumentSolrQuerySet:
    def test_admin_search(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            dqs.admin_search("deed of sale")
            mocksearch.assert_called_with("deed of sale")

    def test_admin_search_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            # ignore + when searching on joins
            dqs.admin_search("CUL Or.1080 3.41 + T-S 13J16.20 + T-S 13J8.14")
            mocksearch.assert_called_with("CUL Or.1080 3.41 T-S 13J16.20 T-S 13J8.14")

    def test_keyword_search_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            # ignore + when searching on joins
            dqs.keyword_search("CUL Or.1080 3.41 + T-S 13J16.20 + T-S 13J8.14")
            mocksearch.assert_called_with("CUL Or.1080 3.41 T-S 13J16.20 T-S 13J8.14")

    def test_keyword_search_field_aliases(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            dqs.keyword_search("pgpid:950 old_pgpid:931 tag:state")
            mocksearch.assert_called_with(
                "pgpid_i:950 old_pgpids_is:931 tags_ss_lower:state"
            )

    def test_keyword_search_field_alias_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            dqs.keyword_search("shelfmark:ena")
            mocksearch.assert_called_with("%sena" % dqs.shelfmark_qf)

    def test_keyword_search_exact_match(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            exact_query = '"six apartments" test'
            dqs.keyword_search(exact_query)
            mocksearch.return_value.raw_query_parameters.return_value.raw_query_parameters.assert_called_with(
                **{
                    "hl.q": "{!type=edismax qf=$keyword_qf pf=$keyword_pf v=$hl_query}",
                    "hl_query": exact_query,
                    "hl.qparser": "lucene",
                }
            )

    def test_get_result_document_images(self):
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

    def test_get_result_document_type(self, document):
        dqs = DocumentSolrQuerySet()
        mock_doc = {
            "type": document.doctype.display_label_en or document.doctype.name_en,
        }
        with patch.object(
            AliasedSolrQuerySet, "get_result_document", return_value=mock_doc
        ):
            # should match a DocumentType by name
            result_doc = dqs.get_result_document(mock_doc)
            print(result_doc["type"])
            assert isinstance(result_doc["type"], DocumentType)

        # special case for Unknown type
        mock_doc = {
            "type": "Unknown type",
        }
        with patch.object(
            AliasedSolrQuerySet, "get_result_document", return_value=mock_doc
        ):
            with patch("geniza.corpus.solr_queryset._") as mock_gettext:
                # should run translate.gettext (in order to get unknown in current language)
                dqs.get_result_document(mock_doc)
                mock_gettext.assert_called_once_with("Unknown type")

        # no match
        mock_doc = {
            "type": "Fake type. Should not match!",
        }
        with patch.object(
            AliasedSolrQuerySet, "get_result_document", return_value=mock_doc
        ):
            # should return the original string
            result_doc = dqs.get_result_document(mock_doc)
            assert isinstance(result_doc["type"], str)
            assert result_doc["type"] == mock_doc["type"]

    def test_search_term_cleanup__nonbool(self):
        dqs = DocumentSolrQuerySet()
        # confirm BL OR is revised to avoid
        dqs._search_term_cleanup("BL OR 5565") == "BL or 5565"
        dqs._search_term_cleanup("BL   OR") == "BL or"
        # when OR doesn't occur alone, it's left as is
        dqs._search_term_cleanup("BL ORNERRY") == "BL ORNERY"

    def test_search_term_cleanup__arabic_to_ja(self):
        dqs = DocumentSolrQuerySet()
        # confirm arabic to judaeo-arabic runs here
        dqs._search_term_cleanup("دينار") == "(دينار|דיהאר)"

    def test_search_term_cleanup__exact_match_regex(self):
        dqs = DocumentSolrQuerySet()
        # double quotes scoped to fields should not become scoped to content_nostem field
        assert "content_nostem" not in dqs._search_term_cleanup('shelfmark:"T-S NS"')
        assert "content_nostem" not in dqs._search_term_cleanup(
            'tag:"marriage payment" shelfmark:"T-S NS"'
        )

        # double quotes for fuzzy/proximity searches should also not be scoped
        assert "content_nostem" not in dqs._search_term_cleanup('"divorced"~20')
        assert "content_nostem" not in dqs._search_term_cleanup('"he divorced"~20')

        # double quotes at the beginning of the query or after a space should be scoped (as well
        # as repeated as an unscoped query)
        assert (
            dqs._search_term_cleanup('"he divorced"') == 'content_nostem:"he divorced"'
        )

        assert 'content_nostem:"he divorced"' in dqs._search_term_cleanup(
            'shelfmark:"T-S NS" "he divorced"'
        )

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

    def test_clean_html(self):
        # minimal prettifier; introduces whitespace changes
        assert clean_html("<li>foo").replace("\n", "") == "<li> foo</li>"

    def test_get_highlighting(self):
        dqs = DocumentSolrQuerySet()
        # no highlighting
        with patch("geniza.corpus.solr_queryset.super") as mock_super:
            mock_get_highlighting = mock_super.return_value.get_highlighting
            mock_get_highlighting.return_value = {}
            assert dqs.get_highlighting() == {}

            # highlighting but no transcription
            test_highlight = {"doc.1": {"description": ["foo bar baz"]}}
            mock_get_highlighting.return_value = test_highlight
            # returned unchanged
            assert dqs.get_highlighting() == test_highlight

            # transcription highlight
            test_highlight = {"doc.1": {"transcription": ["<li>foo"]}}
            mock_get_highlighting.return_value = test_highlight
            # transcription html should be cleaned
            cleaned_highlight = dqs.get_highlighting()
            assert cleaned_highlight["doc.1"]["transcription"] == [
                clean_html("<li>foo")
            ]

            # translation highlight
            test_highlight = {"doc.1": {"translation": ["<li>bar baz"]}}
            mock_get_highlighting.return_value = test_highlight
            # translation html should be cleaned
            cleaned_highlight = dqs.get_highlighting()
            assert cleaned_highlight["doc.1"]["translation"] == [
                clean_html("<li>bar baz")
            ]
