import html
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup
from django.core.paginator import Paginator
from django.http.request import HttpRequest, QueryDict
from django.template.defaultfilters import linebreaks
from django.template.loader import get_template
from django.urls import reverse
from parasolr.django import SolrClient
from pytest_django.asserts import assertContains, assertNotContains, assertTemplateUsed

from geniza.annotations.models import Annotation
from geniza.corpus.admin import DocumentDatingInline
from geniza.corpus.models import Dating, Document, LanguageScript
from geniza.corpus.templatetags.corpus_extras import shelfmark_wrap
from geniza.footnotes.models import Footnote, SourceLanguage


@patch("geniza.corpus.models.GenizaManifestImporter", Mock())
class TestDocumentDetailTemplate:
    def test_shelfmark(self, client, document):
        """Document detail template should include shelfmark"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "CUL Add.2586", html=True)

    def test_doctype(self, client, document):
        """Document detail template should include document type"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "Legal document", html=True)

    def test_first_input(self, client, document):
        """Document detail template should include document first input date"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "In PGP since 2004")

    def test_old_shelfmarks(self, client, document):
        """Document detail template should include historical shelfmarks"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "ULC Add. 2586")

    def test_tags(self, client, document):
        """Document detail template should include all document tags"""
        response = client.get(document.get_absolute_url())
        for tag in ["bill of sale", "real estate"]:
            assertContains(
                response,
                "<li><a href='/en/documents/?q=tag:\"%(tag)s\"' rel='tag'>%(tag)s</li>"
                % {"tag": tag},
                html=True,
            )

    def test_description(self, client, document):
        """Document detail template should include document description"""
        response = client.get(document.get_absolute_url())
        assertContains(response, f"<p>{document.description}</p>", html=True)

    def test_viewer(self, client, document):
        """Document detail template should include viewer for image/transcription content"""
        response = client.get(document.get_absolute_url())
        assertContains(
            response,
            '<section id="itt-panel" data-controller="ittpanel transcription" data-action="click@document->transcription#clickCloseDropdown">',
        )

    def test_viewer_annotations(self, client, document, unpublished_editions):
        """Document detail template should configure image/transcription viewer for annotation display"""
        # fixture does not have annotations
        response = client.get(document.get_absolute_url())
        assertNotContains(
            response,
            '<input type="checkbox" class="toggle" id="transcription-on" data-ittpanel-target="toggle" data-action="ittpanel#clickToggle"  checked="true" aria-label="show transcription">',
            html=True,
        )

        # add a footnote with a digital edition
        Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation={Footnote.DIGITAL_EDITION},
        )
        response = client.get(document.get_absolute_url())
        assertContains(
            response,
            '<input type="checkbox" class="toggle" id="transcription-on" data-ittpanel-target="toggle" data-action="ittpanel#clickToggle" checked="true" aria-label="show transcription">',
            html=True,
        )

        # add a footnote with a digital translation
        hebrew = SourceLanguage.objects.get(name="Hebrew")
        unpublished_editions.languages.add(hebrew)
        translation = Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation=[Footnote.DIGITAL_TRANSLATION],
        )
        response = client.get(document.get_absolute_url())
        # should contain header label for this translation
        assertContains(
            response,
            f'<span data-transcription-target="translationShortLabel" data-ittpanel-target="shortLabel">Translator: {unpublished_editions.all_authors()} {unpublished_editions.all_languages()}</span>',
            html=True,
        )

        # add an annotation to the translation so we can show the next part of the template
        # (looping over canvases to display translation content)
        Annotation.objects.create(
            footnote=translation,
            content={
                "body": [
                    {
                        "value": "test",
                    },
                ],
                "target": {
                    "source": {
                        "id": "fake_canvas",
                    },
                },
                "motivation": ["sc:supplementing", "translating"],
            },
        )
        response = client.get(document.get_absolute_url())
        # should contain rtl and language code, since this is a translation to hebrew
        # NOTE: had to use BeautifulSoup here due to inexplicable failures with assertContains,
        # possibly Unicode-related.
        soup = BeautifulSoup(response.content)
        translation_div = soup.find("div", class_=f"translation tr-{translation.pk}")
        assert translation_div["lang"] == hebrew.code
        assert translation_div["dir"] == "rtl"

    def test_no_viewer(self, client, document):
        """Document with no IIIF shouldn't include viewer in template"""
        # remove fragment IIIF url
        fragment = document.fragments.first()
        fragment.iiif_url = ""
        fragment.save()
        response = client.get(document.get_absolute_url())
        assertNotContains(response, '<div class="wrapper">')

    def test_edit_link(self, client, admin_client, document):
        """Edit link should appear if user is admin, otherwise it should not"""
        edit_url = reverse("admin:corpus_document_change", args=[document.id])
        response = client.get(document.get_absolute_url())
        assertNotContains(response, edit_url)
        response = admin_client.get(document.get_absolute_url())
        assertContains(response, edit_url)

    def test_shelfmarks(self, client, document, join, fragment, multifragment):
        # Ensure that shelfmarks are displayed on the page.
        response = client.get(document.get_absolute_url())
        assertContains(response, "<dt>Shelfmark</dt>", html=True)
        # remove IIIF urls from fixture document fragments to prevent trying to access fake URLs
        fragment.iiif_url = ""
        fragment.save()
        multifragment.iiif_url = ""
        multifragment.save()
        response = client.get(join.get_absolute_url())
        assertContains(response, "<dt>Shelfmark</dt>", html=True)
        assertContains(response, shelfmark_wrap(join.shelfmark), html=True)

    @pytest.mark.skip(reason="temporarily disabled feature")
    def test_download_transcription_link_anonymous(
        self, client, document, unpublished_editions
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        response = client.get(document.get_absolute_url())
        # unpublished editions fixture authored by Goitein
        # should not be available to anonymous users (suppressed for now)
        assertNotContains(response, "Download Goitein's edition")

    # NOTE: text download is limited to authenticated users for now
    @pytest.mark.skip(reason="temporarily disabled feature")
    def test_download_transcription_link(
        self, admin_client, document, unpublished_editions
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        response = admin_client.get(document.get_absolute_url())
        # unpublished editions fixture authored by Goitein
        assertContains(response, "Download Goitein's edition")
        assertContains(
            response,
            reverse(
                "corpus:document-transcription-text",
                kwargs={"pk": document.pk, "transcription_pk": edition.pk},
            ),
        )

    @pytest.mark.skip(reason="temporarily disabled feature")
    def test_download_transcription_link_two_authors(
        self, admin_client, document, twoauthor_source
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        response = admin_client.get(document.get_absolute_url())
        assertContains(response, "Download Kernighan and Ritchie's edition")

    @pytest.mark.skip(reason="temporarily disabled feature")
    def test_download_transcription_link_many_authors(
        self, admin_client, document, multiauthor_untitledsource
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=multiauthor_untitledsource,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        response = admin_client.get(document.get_absolute_url())
        assertContains(
            response, "Download Khan, el-Leithy, Rustow and Vanthieghem's edition"
        )

    def test_languages_none(self, client, document):
        response = client.get(document.get_absolute_url())
        assertNotContains(response, "Primary Language")
        assertNotContains(response, "Secondary Language")

    def test_languages_primary(self, client, document):
        judeo_arabic = LanguageScript.objects.create(
            language="Judaeo-Arabic", script="Hebrew"
        )
        # add a language
        document.languages.add(judeo_arabic)
        response = client.get(document.get_absolute_url())
        # should have one primary language
        assertContains(response, "Primary Language")
        assertContains(response, str(judeo_arabic))
        # not plural, no secondary language
        assertNotContains(response, "Primary Languages")
        assertNotContains(response, "Secondary Language")

        # add a second language
        arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
        document.languages.add(arabic)
        response = client.get(document.get_absolute_url())
        assertContains(response, "Primary Languages")
        assertContains(response, str(judeo_arabic))
        assertContains(response, str(arabic))

    def test_languages_secondary(self, client, document):
        judeo_arabic = LanguageScript.objects.create(
            language="Judaeo-Arabic", script="Hebrew"
        )
        # add a secondary language
        document.secondary_languages.add(judeo_arabic)
        response = client.get(document.get_absolute_url())
        # should have one secondary language
        assertContains(response, "Secondary Language")
        assertContains(response, str(judeo_arabic))
        # not plural, no primary language (not likely in real life, but test logic)
        assertNotContains(response, "Primary Language")
        assertNotContains(response, "Secondary Languages")

        # add a second secondary language
        arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
        document.secondary_languages.add(arabic)
        response = client.get(document.get_absolute_url())
        assertContains(response, "Secondary Languages")
        assertContains(response, str(judeo_arabic))
        assertContains(response, str(arabic))

    def test_inferred_dates(self, client, document):
        # add a dating
        dating = Dating.objects.create(document=document, display_date="c. 1050")
        response = client.get(document.get_absolute_url())
        # should have one inferred date
        assertContains(response, "Inferred Date")
        assertNotContains(response, "Inferred Dates")
        assertContains(response, str(dating.display_date))
        # add a second dating
        dating2 = Dating.objects.create(document=document, display_date="11th century")
        response = client.get(document.get_absolute_url())
        # should have two inferred dates
        assertContains(response, "Inferred Dates")
        assertContains(response, str(dating.display_date))
        assertContains(response, str(dating2.display_date))


class TestDocumentScholarshipTemplate:
    def test_source_title(self, client, document, twoauthor_source):
        """Document scholarship template should show source titles if present"""
        Footnote.objects.create(content_object=document, source=twoauthor_source)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "<em>The C Programming Language</em>")
        twoauthor_source.title_en = ""
        twoauthor_source.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, "<em>The C Programming Language</em>")

    def test_source_authors(self, client, document, twoauthor_source):
        """Document scholarship template should show source authors if present"""
        Footnote.objects.create(content_object=document, source=twoauthor_source)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "Brian Kernighan and Dennis Ritchie")
        for author in twoauthor_source.authors.all():
            twoauthor_source.authors.remove(author)
        twoauthor_source.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, "Brian Kernighan and Dennis Ritchie")

    def test_source_date(self, client, document, article):
        """Document scholarship template should show source pub. year if present"""
        Footnote.objects.create(content_object=document, source=article)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "(n.p., 1963)")
        article.year = None
        article.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, "(n.p., 1963)")

    def test_source_url(self, client, document, article):
        """Document scholarship template should show source URL if present"""
        fn = Footnote.objects.create(
            content_object=document, source=article, url="https://example.com/"
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response, '<a href="https://example.com/">online resource</a>', html=True
        )
        fn.url = ""
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, '<a href="https://example.com/">')

    def test_source_relation(self, client, document, source, twoauthor_source):
        """Document scholarship template should show source relation to doc"""
        fn = Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.EDITION
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "<li>Edition</li>", html=True)

        fn2 = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.EDITION,
            location="p. 25",
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "<li>Edition</li>", html=True)

        fn2.doc_relation = [Footnote.EDITION, Footnote.TRANSLATION]
        fn2.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response,
            "<li>Edition</li>",
            html=True,
        )
        print(response.content)
        assertContains(
            response,
            "<li>Translation</li>",
            html=True,
        )

    def test_source_location(self, client, document, source):
        """Document scholarship template should show footnote location when present"""
        fn = Footnote.objects.create(
            content_object=document,
            source=source,
            location="p. 25",
            doc_relation=Footnote.EDITION,
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "<li>p. 25</li>", html=True)
        fn.location = ""
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, "p. 25")  # should not show when removed

    def test_whats_in_pgp(self, client, document, source, unpublished_editions):
        """Document detail template should show what's in the PGP"""
        # has no image, transcription or translation
        empty_doc = Document.objects.create()
        response = client.get(empty_doc.get_absolute_url())
        assertNotContains(response, "What's in the PGP")

        # has image but no transcription or translation
        response = client.get(document.get_absolute_url())
        assertContains(response, "What's in the PGP")
        assertContains(response, '<li class="has-image">Image</li>')
        assertNotContains(response, '<li class="transcription-count">')
        assertNotContains(response, '<li class="translation-count">')

        # add a footnote with a digital edition
        Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        response = client.get(document.get_absolute_url())
        assertContains(response, '<li class="transcription-count">')
        assertContains(response, "1 Transcription")

        # add two footnotes with digital translation
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=[Footnote.DIGITAL_TRANSLATION],
        )
        Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation=[Footnote.DIGITAL_TRANSLATION],
        )
        response = client.get(document.get_absolute_url())
        assertContains(response, "2 Translations")


class TestDocumentTabsSnippet:
    def test_detail_link(self, client, document):
        """document nav tabs should always include doc detail page link"""
        response = client.get(document.get_absolute_url())
        assertContains(response, document.get_absolute_url())

    def test_no_footnotes(self, client, document):
        """document nav should render inert scholarship tab if no footnotes"""
        response = client.get(document.get_absolute_url())
        # uses span, not link
        assertContains(
            response,
            "<span disabled aria-disabled='true'>Select Bibliography (0)</span>",
            html=True,
        )

    def test_with_footnotes(self, client, document, source, twoauthor_source):
        """document nav should render scholarship link with footnote counter"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(document.get_absolute_url())

        # renders link to scholarship records page
        assertContains(
            response, reverse("corpus:document-scholarship", args=[document.pk])
        )
        # count should be 1
        assertContains(response, "Select Bibliography (1)")

        Footnote.objects.create(content_object=document, source=twoauthor_source)
        response = client.get(document.get_absolute_url())

        # count should be 2
        assertContains(response, "Select Bibliography (2)")

    def test_no_related_docs(self, client, document, empty_solr):
        """document nav should render disabled related documents tab if no related documents"""
        response = client.get(document.get_absolute_url())
        # uses span, not link
        assertContains(
            response,
            "<span disabled aria-disabled='true'>Related Documents (0)</span>",
            html=True,
        )

    def test_with_related_docs(self, client, document, join, empty_solr):
        """document nav should render related docs link with count"""
        Document.index_items([document, join])
        SolrClient().update.index([], commit=True)
        response = client.get(document.get_absolute_url())

        # count should be 1
        assertContains(response, "Related Documents (1)")


class TestDocumentResult:
    template = get_template("corpus/snippets/document_result.html")
    page_obj = Paginator([1], 1).page(1)

    def test_no_scholarship_records(self):
        assert "No Scholarship Records" in self.template.render(
            context={
                "document": {"pgpid": 1, "id": "document.1", "shelfmark": "MS a"},
                "highlighting": {},
                "page_obj": self.page_obj,
            }
        )

    def test_has_scholarship_records(self):
        result = self.template.render(
            context={
                "document": {
                    "pgpid": 1,
                    "id": "document.1",
                    "shelfmark": "MS 12",
                    "num_editions": 15,
                    "scholarship_count": 10,
                },
                "highlighting": {},
                "page_obj": self.page_obj,
            }
        )
        assert "No Scholarship Records" not in result
        assert "15 Transcriptions" in result
        assert "Translation" not in result
        assert "Discusion" not in result

    def test_tags(self):
        tags = ["bill of sale", "real estate"]
        result = self.template.render(
            context={
                "document": {
                    "pgpid": 1,
                    "id": "document.1",
                    "tags": tags,
                    "shelfmark": "MS 1",
                },
                "highlighting": {},
                "page_obj": self.page_obj,
            }
        )
        for tag in tags:
            assert (
                "<li><a href='/en/documents/?q=tag:\"%(tag)s\"'>%(tag)s</a></li>"
                % {"tag": tag}
                in result
            )

        # Ensure that the number of tags shown is limited to 5 and message displays correctly
        tags = ["bill of sale", "real estate", "arabic", "ib6", "ibn", "red sea"]
        result = self.template.render(
            context={
                "document": {
                    "pgpid": 1,
                    "id": "document.1",
                    "tags": tags,
                    "shelfmark": "ms a",
                },
                "highlighting": {},
                "page_obj": self.page_obj,
            }
        )
        assert "red sea" not in result
        assert "+ 1 more" in result

    def test_multiple_scholarship_types(self):
        result = self.template.render(
            context={
                "document": {
                    "pgpid": 1,
                    "shelfmark": "JRL Series A 1",
                    "id": "document.1",
                    "num_editions": 2,
                    "num_translations": 1,
                    "num_discussions": 2,
                    "scholarship_count": 10,
                },
                "highlighting": {},
                "page_obj": self.page_obj,
            },
        )
        assert "2 Transcriptions" in result
        assert "1 Translation" in result
        assert "2 Discussions" in result

    def test_description(self, document):
        context = {
            "document": {
                "pgpid": document.id,
                "id": "document.%d" % document.id,
                "description": [document.description],
                "shelfmark": "ms heb ab",
            },
            # no highlighting at all (i.e., no keyword search)
            "highlighting": {},
            "page_obj": self.page_obj,
        }

        # template currently has truncate words 25; just check that the beginning
        # of the description is there
        assert document.description[:50] in self.template.render(context)

        # if there is highlighting but not for this document,
        # description excerpt should still display
        #  (solr returns empty list if there are no keywords)
        context["highlighting"] = {"document.%d" % document.id: {"description": []}}
        assert document.description[:50] in self.template.render(context)

    def test_description_highlighting(self, document):
        test_highlight = "passage of the <em>Tujib<em> quarter"
        result = self.template.render(
            context={
                "document": {
                    "pgpid": document.id,
                    "id": "document.%d" % document.id,
                    "shelfmark": "ms heb 3",
                },
                "highlighting": {
                    "document.%d" % document.id: {"description": [test_highlight]}
                },
                "page_obj": self.page_obj,
            }
        )
        # keywords in context displayed instead of description excerpt
        assert test_highlight in result
        assert document.description[:50] not in result

    def test_transcription(self, document):
        transcription_txt = """שהדותא דהוה באנפנא אנן שהדי דחתימין לתחתא בשטר זביני דנן
בתלתא בשבה דהוה ח…"""
        context = {
            "document": {
                "pgpid": document.id,
                "id": "document.%d" % document.id,
                "shelfmark": "ms abc",
                "transcription": [transcription_txt],
            },
            "highlighting": {},
            "page_obj": self.page_obj,
        }

        # template currently has truncate chars 150; just check that the beginning
        # of the transcription is there
        rendered = self.template.render(context)
        assert transcription_txt[:150] in rendered
        # language not specified
        assert 'lang=""' in rendered
        # language script not specified if unset
        assert "data-lang-script" not in rendered

        # use language code & script, when specified
        context["document"]["language_code"] = "jrb"
        context["document"]["language_script"] = "Hebrew"
        rendered = self.template.render(context)
        assert 'lang="jrb"' in rendered
        assert 'data-lang-script="hebrew"' in rendered

    def test_transcription_highlighting(self, document):
        test_highlight = "<em>לסידנא</em> אלרב ותערפני וצולהא פי רסאלתך אן שא אללה"
        transcription_txt = """שהדותא דהוה באנפנא אנן שהדי דחתימין לתחתא בשטר זביני דנן
בתלתא בשבה דהוה ח…"""
        result = self.template.render(
            context={
                "document": {
                    "pgpid": document.id,
                    "id": "document.%d" % document.id,
                    "shelfmark": "ms abc",
                    "transcription": [transcription_txt],
                    "lang": ["jrb"],
                },
                "highlighting": {
                    "document.%d"
                    % document.id: {"transcription": [{"text": test_highlight}]}
                },
                "page_obj": self.page_obj,
            }
        )
        # keywords in context displayed instead of description excerpt
        assert test_highlight in result
        assert transcription_txt[:75] not in result


class TestSearchPagination:
    template = get_template("corpus/snippets/pagination.html")

    def test_one_page(self):
        paginator = Paginator(range(5), per_page=5)
        ctx = {"page_obj": paginator.page(1), "request": HttpRequest()}
        result = self.template.render(ctx)
        assert '<nav class="pagination' in result
        assert '<span class="disabled prev">' in result
        assert '<a title="page 1" class="pagelink" aria-current="page"' in result
        assert '<span class="disabled next">' in result

    def test_first_of_twenty_pages(self):
        paginator = Paginator(range(20), per_page=1)
        ctx = {"page_obj": paginator.page(1), "request": HttpRequest()}
        result = self.template.render(ctx)
        assert '<span class="disabled prev">' in result
        assert '<a title="page 1" class="pagelink" aria-current="page"' in result
        assert '<a title="page 2" class="pagelink" href="?page=2">' in result
        assert (
            '<a name="Next" title="Next" class="next" rel="next" href="?page=2">'
            in result
        )

    def test_tenth_of_twenty_pages(self):
        paginator = Paginator(range(20), per_page=1)
        ctx = {"page_obj": paginator.page(10), "request": HttpRequest()}
        result = self.template.render(ctx)
        assert (
            '<a name="Previous" title="Previous" class="prev" rel="prev" href="?page=9">'
            in result
        )
        assert '<a title="page 10" class="pagelink" aria-current="page"' in result
        assert '<a title="page 11" class="pagelink" href="?page=11">' in result
        assert (
            '<a name="Next" title="Next" class="next" rel="next" href="?page=11">'
            in result
        )

    def test_with_query_param(self):
        paginator = Paginator(range(20), per_page=1)
        req = HttpRequest()
        req.GET = QueryDict("?q=contract")
        ctx = {"page_obj": paginator.page(10), "request": req}
        result = self.template.render(ctx)
        assert f"q=contract&page=9" in html.unescape(result)


class TestRelatedDocumentsTemplate:
    def test_related_list(self, client, document, join, empty_solr):
        """should render results list for related documents"""
        Document.index_items([document, join])
        SolrClient().update.index([], commit=True)

        response = client.get(reverse("corpus:related-documents", args=(document.id,)))
        assertContains(
            response, '<section id="document-list" class="related-documents">'
        )
        assertContains(response, "<ol>")

        # list should have at least one item
        assertContains(response, '<li class="search-result"')

        # "join" fixture should be in list
        assertContains(response, f"<dd>{join.id}</dd>")


class TestFieldsetSnippet:
    """Unit tests for the override of django admin/includes/mixed_inlines_fieldsets.html, which allows
    inclusion of inline formsets between model form fields"""

    template = "admin/snippets/mixed_inlines_fieldsets.html"

    def test_inlines_included(self, admin_client, document):
        # the snippet should be included on the admin document change page
        response = admin_client.get(
            reverse("admin:corpus_document_change", args=(document.id,))
        )
        assertTemplateUsed(response, template_name=self.template)

        # should include Dating inline
        assertTemplateUsed(response, template_name=DocumentDatingInline.template)
        assertContains(
            response,
            '<fieldset class="module sortable" aria-labelledby="textblock_set-heading">',
        )

        # Dating inline should be immediately after fieldset containing standard_date
        soup = BeautifulSoup(response.content)
        date_fieldset = soup.find("div", class_="field-standard_date").find_parent(
            "fieldset"
        )
        assert date_fieldset.find_next_sibling("div")["id"] == "dating_set-group"
        dating_inline = soup.find("div", id="dating_set-group")
        assert not dating_inline.find_parent("fieldset")

        # should include other inlines outside of form fieldsets
        assertContains(
            response,
            '<fieldset class="module sortable" aria-labelledby="textblock_set-heading">',
        )
        textblock_set_inline = soup.find("div", id="textblock_set-group")
        assert not textblock_set_inline.find_parent("fieldset")
