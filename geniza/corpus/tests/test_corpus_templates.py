import html
from unittest.mock import Mock, patch

import pytest
from django.core.paginator import Paginator
from django.http.request import HttpRequest, QueryDict
from django.template.defaultfilters import linebreaks
from django.template.loader import get_template
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from geniza.corpus.models import Document, LanguageScript, TextBlock
from geniza.footnotes.models import Footnote


@patch("geniza.corpus.models.ManifestImporter", Mock())
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
        # NOTE: No longer using definition list
        print(response.content)
        assertContains(response, "In PGP since 2004")

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
        """Document detail template should include viewer for IIIF content"""
        response = client.get(document.get_absolute_url())
        assertContains(
            response,
            '<section id="iiif-viewer" data-controller="iiif">',
        )

    def test_viewer_annotations(self, client, document, unpublished_editions):
        """Document detail template should configure IIIF viewer for annotation display"""
        # fixture does not have annotations
        response = client.get(document.get_absolute_url())
        assertNotContains(response, '<div class="transcription">')

        # add a footnote with a digital edition
        Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation={Footnote.EDITION},
            content={"text": "A piece of text"},
        )
        response = client.get(document.get_absolute_url())
        assertContains(response, '<div class="transcription">')

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

    def test_editors(self, client, document, source, twoauthor_source):
        # footnote with no content
        Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.EDITION
        )
        # No digital editions, so no editors
        response = client.get(document.get_absolute_url())
        assertNotContains(response, "Editor")

        # footnote with one author, content
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation={Footnote.EDITION, Footnote.TRANSLATION},
            content={"text": "A piece of text"},
        )

        # Digital edition with one author, should have one editor but not multiple
        response = client.get(document.get_absolute_url())
        assertContains(response, "Editor")
        assertNotContains(response, "Editors")

        # footnote with two authors, content
        Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.EDITION,
            content={"text": "B other text"},
        )
        # Should now be "editors"
        response = client.get(document.get_absolute_url())
        assertContains(response, "Editors")

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
        shelfmarks = join.certain_join_shelfmarks
        assertContains(
            response,
            "<span>%s + </span><span>%s</span>" % (shelfmarks[0], shelfmarks[1]),
            html=True,
        )

    def test_download_transcription_link_anonymous(
        self, client, document, unpublished_editions
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation=Footnote.EDITION,
            content={
                "html": "some transcription text",
                "text": "some transcription text",
            },
        )
        response = client.get(document.get_absolute_url())
        # unpublished editions fixture authored by Goitein
        # should not be available to anonymous users (suppressed for now)
        assertNotContains(response, "Download Goitein's edition")

    # NOTE: text download is limited to authenticated users for now
    def test_download_transcription_link(
        self, admin_client, document, unpublished_editions
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=unpublished_editions,
            doc_relation=Footnote.EDITION,
            content={
                "html": "some transcription text",
                "text": "some transcription text",
            },
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

    def test_download_transcription_link_two_authors(
        self, admin_client, document, twoauthor_source
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.EDITION,
            content={
                "html": "some transcription text",
                "text": "some transcription text",
            },
        )
        response = admin_client.get(document.get_absolute_url())
        assertContains(response, "Download Kernighan and Ritchie's edition")

    def test_download_transcription_link_many_authors(
        self, admin_client, document, multiauthor_untitledsource
    ):
        edition = Footnote.objects.create(
            content_object=document,
            source=multiauthor_untitledsource,
            doc_relation=Footnote.EDITION,
            content={
                "html": "some transcription text",
                "text": "some transcription text",
            },
        )
        response = admin_client.get(document.get_absolute_url())
        assertContains(
            response, "Download Khan, el-Leithy, Rustow and Vanthieghem's edition"
        )

    def test_other_docs_none(self, document, client):
        """If there are no other documents, don't show the other docs section"""
        response = client.get(document.get_absolute_url())
        assertNotContains(response, "Other documents on this fragment")

    def test_other_docs(self, document, join, client):
        """If there are other documents, show the other docs section"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "Other documents on this fragment")
        assertContains(response, join.get_absolute_url())
        assertContains(response, join.title)

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
        assertContains(
            response, '<dt class="relation">includes edition</dt>', html=True
        )

        fn2 = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.EDITION,
            location="p. 25",
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, '<dt class="relation">for edition see</dt>', html=True)

        fn2.doc_relation = [Footnote.EDITION, Footnote.TRANSLATION]
        fn2.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        print(response.content)
        assertContains(
            response,
            '<dt class="relation">for edition, translation see</dt>',
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
        assertContains(response, "p. 25")
        fn.location = ""
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, "p. 25")  # should not show when removed


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
            "<span disabled aria-disabled='true'>Scholarship Records (0)</span>",
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
        assertContains(response, "Scholarship Records (1)")

        Footnote.objects.create(content_object=document, source=twoauthor_source)
        response = client.get(document.get_absolute_url())

        # count should be 2
        assertContains(response, "Scholarship Records (2)")

    def test_external_link_disabled(self, client, document, fragment):
        """document nav should render external links as disabled (for MVP)"""
        # remove default URL from fragment
        fragment.url = ""
        fragment.save()
        response = client.get(document.get_absolute_url())

        # disabled (not yet implemented) for MVP
        assertContains(
            response,
            "<li><span disabled aria-disabled='true'>External Links</span></li>",
            html=True,
        )

    @pytest.mark.skip("non-MVP feature")
    def test_no_links(self, client, document, fragment):
        """document nav should render inert links tab if no external links"""
        # remove default URL from fragment
        fragment.url = ""
        fragment.save()
        response = client.get(document.get_absolute_url())

        # uses span, not link
        assertContains(response, "<span>External Links (0)</span>", html=True)

    @pytest.mark.skip("non-MVP feature")
    def test_with_links(self, client, document, multifragment):
        """document nav should render external links link with link counter"""
        response = client.get(document.get_absolute_url())

        # TODO renders link to external links page
        # assertContains(
        #     response, reverse("corpus:document-scholarship", args=[document.pk])
        # )

        # count should be 1
        assertContains(response, "External Links (1)")

        # associate to another fragment with a URL
        TextBlock.objects.create(document=document, fragment=multifragment)
        response = client.get(document.get_absolute_url())

        # count should be 2
        assertContains(response, "External Links (2)")


class TestDocumentResult:

    template = get_template("corpus/snippets/document_result.html")
    page_obj = Paginator([1], 1).page(1)

    def test_no_scholarship_records(self):
        assert "No Scholarship Records" in self.template.render(
            context={
                "document": {"pgpid": 1, "id": "document.1"},
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
                "document": {"pgpid": 1, "id": "document.1", "tags": tags},
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
                "document": {"pgpid": 1, "id": "document.1", "tags": tags},
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
                "document": {"pgpid": document.id, "id": "document.%d" % document.id},
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
                "transcription": [transcription_txt],
            },
            "highlighting": {},
            "page_obj": self.page_obj,
        }

        # template currently has truncate chars 150; just check that the beginning
        # of the transcription is there
        rendered = self.template.render(context)
        assert linebreaks(transcription_txt)[:150] in rendered
        # language not specified
        assert 'lang=""' in rendered

        # use first language code, if specified
        context["document"]["language_code"] = ["jrb", "ara"]
        rendered = self.template.render(context)
        assert 'lang="jrb"' in rendered

    def test_transcription_highlighting(self, document):
        test_highlight = "<em>לסידנא</em> אלרב ותערפני וצולהא פי רסאלתך אן שא אללה"
        transcription_txt = """שהדותא דהוה באנפנא אנן שהדי דחתימין לתחתא בשטר זביני דנן
בתלתא בשבה דהוה ח…"""
        result = self.template.render(
            context={
                "document": {
                    "pgpid": document.id,
                    "id": "document.%d" % document.id,
                    "transcription": [transcription_txt],
                    "lang": ["jrb"],
                },
                "highlighting": {
                    "document.%d" % document.id: {"transcription": [test_highlight]}
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
