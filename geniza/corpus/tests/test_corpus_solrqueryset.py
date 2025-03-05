from unittest.mock import patch

import pytest
from parasolr.django import AliasedSolrQuerySet, SolrClient
from piffle.image import IIIFImageClient

from geniza.corpus.models import Document, DocumentType, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet, clean_html


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

    def test_admin_search_nested_edismax(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            # scoped search with edismax subquery should use uf="* _query_" workaround
            dqs.admin_search('shelfmark:"T-S 13J8.14"')
            mocksearch.return_value.raw_query_parameters.assert_called_with(
                doc_query='%s"T-S 13J8.14"' % dqs.shelfmark_qf, uf="* _query_"
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
                keyword_query="%sena" % dqs.shelfmark_qf,
                uf="* _query_",  # solr 7.2 workaround for nested edismax
            )

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

    @pytest.mark.django_db
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
            # should produce a list of 2 tuples, each containing a IIIFImageClient, label str,
            # and rotation int, from above dict
            assert len(result_imgs) == 2
            assert isinstance(result_imgs[0][0], IIIFImageClient)
            assert (
                result_imgs[0][0].info()
                == "http://example.co/iiif/ts-1/00001/info.json"
            )
            assert result_imgs[0][1] == "1r"
            # when no rotations in mock doc (i.e. indexed prior to rotation override), should be 0
            assert result_imgs[0][2] == 0

        # with rotations
        dqs = DocumentSolrQuerySet()
        mock_doc = {
            "iiif_images": ["http://example.co/iiif/1", "http://example.co/iiif/2"],
            "iiif_labels": ["1r", "1v"],
            "iiif_rotations": [90, 180],
        }
        with patch.object(
            AliasedSolrQuerySet, "get_result_document", return_value=mock_doc
        ):
            result_doc = dqs.get_result_document(mock_doc)
            result_imgs = result_doc["iiif_images"]
            # should set rotation as 3rd entry in each tuple
            assert result_imgs[0][2] == 90

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
        # confirm arabic to judaeo-arabic runs here (with boost)
        assert dqs._search_term_cleanup("دينار") == "(دينار^100.0 OR דינאר)"
        # confirm arabic to judaeo-arabic does not run here
        assert (
            dqs._search_term_cleanup('"دي[نا]ر"')
            == '(description_nostem:"دي[نا]ر" OR transcription_nostem:"دي[نا]ر")'
        )

    def test_search_term_cleanup__exact_match_regex(self):
        dqs = DocumentSolrQuerySet()
        # double quotes scoped to fields should not become scoped to nostem fields
        assert "description_nostem" not in dqs._search_term_cleanup(
            'shelfmark:"T-S NS"'
        )
        assert "description_nostem" not in dqs._search_term_cleanup(
            'tag:"marriage payment" shelfmark:"T-S NS"'
        )

        # double quotes for fuzzy/proximity searches should also not be scoped
        assert "description_nostem" not in dqs._search_term_cleanup('"divorced"~20')
        assert "description_nostem" not in dqs._search_term_cleanup('"he divorced"~20')

        # double quotes at the beginning of the query or after a space should be scoped (as well
        # as repeated as an unscoped query)
        assert (
            dqs._search_term_cleanup('"he divorced"')
            == '(description_nostem:"he divorced" OR transcription_nostem:"he divorced")'
        )

        assert 'description_nostem:"he divorced"' in dqs._search_term_cleanup(
            'shelfmark:"T-S NS" "he divorced"'
        )

        # should preserve order for e.g. boolean searches with exact matches
        assert (
            dqs._search_term_cleanup('"מרכב אלצלטאן" AND "אלמרכב אלצלטאן"')
            == '(description_nostem:"מרכב אלצלטאן" OR transcription_nostem:"מרכב אלצלטאן") AND (description_nostem:"אלמרכב אלצלטאן" OR transcription_nostem:"אלמרכב אלצלטאן")'
        )

    def test_search_term_cleanup__quoted_shelfmark_only(self):
        dqs = DocumentSolrQuerySet()
        # double quoted shelfmark-only search should populate dqs.shelfmark_query
        dqs._search_term_cleanup('shelfmark:"T-S NS"')
        assert "T-S NS" in dqs.shelfmark_query

        # otherwise dqs.sheflmark_query should remain unset
        dqs = DocumentSolrQuerySet()
        assert "T-S NS" in dqs._search_term_cleanup(
            'tag:"marriage payment" shelfmark:"T-S NS"'
        )
        assert not dqs.shelfmark_query
        assert "NS" in dqs._search_term_cleanup("shelfmark:NS")
        assert not dqs.shelfmark_query

    def test_handle_hebrew_prefixes(self):
        dqs = DocumentSolrQuerySet()
        # should replace words with hebrew prefixes with OR queries
        # on the same word with or without prefix
        assert dqs._handle_hebrew_prefixes("אלמרכב") == "(אלמרכב OR מרכב)"
        assert (
            dqs._handle_hebrew_prefixes("test one משיח two כבוד")
            == "test one (משיח OR שיח) two (כבוד OR בוד)"
        )
        # when cleanup is applied, will also apply JA to Arabic conversion
        assert (
            dqs._search_term_cleanup("אלמרכב")
            == "((אלמרכב^100.0 OR المركب OR المرخب) OR (מרכב^100.0 OR مركب OR مرخب))"
        )

    def test_keyword_search__quoted_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            # only quoted shelfmark: should only search on shelfmark fields
            dqs.keyword_search('shelfmark:"T-S NS"')
            mocksearch.assert_called_with(dqs.shelfmark_query)
            mocksearch.return_value.raw_query_parameters.assert_not_called()

        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            # otherwise should search as normal
            dqs.keyword_search('tag:"marriage payment" shelfmark:"T-S NS"')
            mocksearch.return_value.raw_query_parameters.assert_called()
            dqs.keyword_search("shelfmark:NS")
            mocksearch.return_value.raw_query_parameters.assert_called()

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
        # whitespace should be unmodified within <li> tags; minimal prettifier in others
        assert clean_html("<li>foo</li><p>bar</p>") == "<li>foo</li>\n<p>\n bar\n</p>"
        # should open and close partial </li> tags
        assert clean_html("<li>foo") == "<li>foo</li>"
        assert clean_html("foo</li>") == "<li>...foo</li>"
        # should insert (value - 1) of first numbered <li>
        assert (
            clean_html('foo</li>\n<li value="3">bar</li>').replace("\n", "")
            == '<li value="2">...foo</li><li value="3">bar</li>'
        )
        # should work with paragraphs (and not insert ellipsis before paragraph)
        assert (
            clean_html('<p>foo</p>\n</li>\n<li value="3">bar</li>').replace("\n", "")
            == '<li value="2"><p>foo</p></li><li value="3">bar</li>'
        )

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
            assert cleaned_highlight["doc.1"]["transcription"][0]["text"] == clean_html(
                "<li>foo"
            )

            # translation highlight
            test_highlight = {"doc.1": {"translation": ["<li>bar baz"]}}
            mock_get_highlighting.return_value = test_highlight
            # translation html should be cleaned
            cleaned_highlight = dqs.get_highlighting()
            assert cleaned_highlight["doc.1"]["translation"] == [
                clean_html("<li>bar baz")
            ]

    def test_get_highlighting__exact_search(self):
        dqs = DocumentSolrQuerySet()
        with patch("geniza.corpus.solr_queryset.super") as mock_super:
            mock_get_highlighting = mock_super.return_value.get_highlighting
            test_highlight = {
                "doc.1": {
                    "description": ["matched"],
                    "description_nostem": ["exactly matched"],
                    "transcription": ["match"],
                    "transcription_nostem": ["exact match"],
                }
            }
            mock_get_highlighting.return_value = test_highlight
            # no exact search was made; returned unchanged
            assert dqs.get_highlighting() == test_highlight

            # an exact search was made; now, the highlighting we actually use in the template
            # ("description" and "transcription" keys) should be replaced w/ the nostem matches
            dqs.raw_params["hl_query"] = "exact match"
            assert dqs.get_highlighting()["doc.1"]["description"] == ["exactly matched"]
            assert dqs.get_highlighting()["doc.1"]["transcription"][0][
                "text"
            ] == clean_html("exact match")

    def test_get_highlighting__old_shelfmark(self):
        dqs = DocumentSolrQuerySet()
        with patch("geniza.corpus.solr_queryset.super") as mock_super:
            mock_get_highlighting = mock_super.return_value.get_highlighting
            test_highlight = {
                "doc.1": {
                    # typical formatting for an old_shelfmark highlight
                    "old_shelfmark": ["", "matched", "secondmatch"],
                }
            }
            mock_get_highlighting.return_value = test_highlight
            # should flatten list with comma separation
            assert (
                dqs.get_highlighting()["doc.1"]["old_shelfmark"]
                == "matched, secondmatch"
            )

            test_highlight = {
                "doc.1": {
                    "old_shelfmark_t": ["", "matched"],
                }
            }
            mock_get_highlighting.return_value = test_highlight
            # should use old_shelfmark_t highlight
            assert dqs.get_highlighting()["doc.1"]["old_shelfmark"] == "matched"

    def test_get_highlighting__regex(self):
        dqs = DocumentSolrQuerySet()
        dqs.search_qs = ["transcription_regex:/.*test.*/"]
        # if regex_query in raw params, should overwrite any normal matches with regex matches
        with patch("geniza.corpus.solr_queryset.super") as mock_super:
            mock_get_highlighting = mock_super.return_value.get_highlighting
            test_highlight = {"document.1": {"transcription": {"text": ["match"]}}}
            mock_get_highlighting.return_value = test_highlight
            with patch.object(dqs, "get_results") as mock_get_results:
                mock_get_results.return_value = [
                    {"id": "document.1", "transcription_regex": ["a test text"]}
                ]
                with patch("geniza.corpus.solr_queryset.clean_html") as mock_clean_html:
                    highlighting = dqs.get_highlighting()
                    assert highlighting != test_highlight
                    assert len(highlighting["document.1"]["transcription"]) == 1
                    assert (
                        "match"
                        not in highlighting["document.1"]["transcription"][0]["text"]
                    )
                    assert (
                        "<em>test</em>"
                        in highlighting["document.1"]["transcription"][0]["text"]
                    )
                    # in regex, clean_html should not be called
                    mock_clean_html.assert_not_called
                    # it should stil be called in other types of searches
                    mock_get_results.return_value = [
                        {"id": "document.1", "transcription_nostem": ["a test text"]}
                    ]
                    mock_clean_html.assert_called_once

    def test_get_highlighting__regex__multitranscription(self):
        dqs = DocumentSolrQuerySet()
        dqs.search_qs = ["transcription_regex:/.*test.*/"]
        with patch.object(dqs, "get_results") as mock_get_results:
            mock_get_results.return_value = [
                {
                    "id": "document.1",
                    "transcription_regex": ["a test text", "testing", "test", "other"],
                    "transcription_regex_names": ["s 1", "s 1", "src2", "src2"],
                }
            ]
            with patch("geniza.corpus.solr_queryset.clean_html") as mock_clean_html:
                highlighting = dqs.get_highlighting()
                # should have 3 matches
                assert len(highlighting["document.1"]["transcription"]) == 3
                # should highlight and place into "text"
                assert (
                    "<em>test</em>"
                    in highlighting["document.1"]["transcription"][0]["text"]
                )
                # labels should be associated in order 1, 1, 2, (2) (though only three matches)
                assert highlighting["document.1"]["transcription"][0]["label"] == "s 1"
                # should dedupe identical label in the second result
                assert "label" not in highlighting["document.1"]["transcription"][1]
                assert highlighting["document.1"]["transcription"][2]["label"] == "src2"

    def test_regex_search(self):
        dqs = DocumentSolrQuerySet()
        with patch.object(dqs, "search") as mocksearch:
            query = "six apartments"
            dqs.regex_search(query)
            # should surround with wildcards in order to match entire field,
            # and with slashes for Lucene regex syntax
            mocksearch.assert_called_with(f"transcription_regex:/.*{query}.*/")

    def test_get_regex_highlight(self):
        dqs = DocumentSolrQuerySet()
        dqs.search_qs = ["transcription_regex:/.*אלאחרף אן למא.*/"]
        # no match -> None
        assert dqs.get_regex_highlight("test") == None
        # use a bit of a real example, with > 300 characters, as a test
        text = """Recto:\n בש רח נקול נחן אלשהוד [אלוא]צעין כטוטנא תחת הדה אלאחרף אן למא אן כאן \
יום אלסבת אלסאדס מן שהר אב יהפך לשמחה שנת אתקו לשטרות בעיר קליוב הסמוכה לעיר המלוכה הס[מו]כה \
לפסטאט מצרים דעל נילוס נהרה מותבה רשותא דאדונינו גאונינו שר שלום הלוי הגאון ראש ישיבת גאון יעקב \
יהי שמו לעולם אנא חצרנא פי אלמוצע אלדי יצלו פיה ענד מוסי ולד אלאהוב וכאן תם חאצר אהל קליוב שצ \
//ביצלו// פחצר תם מן קאל להם אעלמו באן יצחק אלסקלי ביגתהד פי עודתה אליכם פאן כונתו פי נפסכם \
מן מקאמה ענדכם דון """
        highlight = dqs.get_regex_highlight(text)

        # should highlight the matched portion
        assert "<em>אלאחרף אן למא</em>" in highlight

        # should shorten context on either side of match to <=150 characters + 2 words
        assert len(highlight) < len(text)
        before_match = highlight.split("<em>")[0]
        assert len(before_match) <= 175
        after_match = highlight.split("</em>")[1]
        assert len(after_match) <= 175

        # should support all regex syntax, such as . wildcard and + 1 or more characters
        dqs.search_qs = ["transcription_regex:/.*אלאחרף.+למא.*/"]
        highlight = dqs.get_regex_highlight(text)
        assert "<em>אלאחרף אן למא</em>" in highlight

        # reserved characters should require escape characters for correct results
        dqs.search_qs = ["transcription_regex:/.*[אלוא]צעין.*/"]
        highlight = dqs.get_regex_highlight(text)
        assert highlight is None
        dqs.search_qs = ["transcription_regex:/.*\[אלוא\]צעין.*/"]
        highlight = dqs.get_regex_highlight(text)
        assert "<em>[אלוא]צעין</em>" in highlight

        # multiple matches for the query should be separated by line breaks and ellipsis
        dqs.search_qs = ["transcription_regex:/.*מן.*/"]
        highlight = dqs.get_regex_highlight(text)
        separator = "<br />[…]<br />"
        assert separator in highlight

        # multiple matches in the same ~300 chars context should all be highlighted
        # check: there should be two snippets here, but three matches
        hl_snippets = highlight.split(separator)
        assert len(hl_snippets) == 2
        # the first snippet should have one highlight in it
        hl_snippets[0].count("<em>מן</em>") == 1
        # the second snippet should have two highlights in it
        hl_snippets[1].count("<em>מן</em>") == 2
