import html

from django.core.paginator import Paginator
from django.http.request import HttpRequest, QueryDict
from django.template.loader import get_template
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from geniza.corpus.models import TextBlock
from geniza.footnotes.models import Footnote


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
        assertContains(response, '<dd class="secondary">2004</dd>', html=True)

    def test_tags(self, client, document):
        """Document detail template should include all document tags"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "<li>bill of sale</li>", html=True)
        assertContains(response, "<li>real estate</li>", html=True)

    def test_description(self, client, document):
        """Document detail template should include document description"""
        response = client.get(document.get_absolute_url())
        assertContains(response, f"<p>{document.description}</p>", html=True)

    def test_viewer(self, client, document):
        """Document detail template should include viewer for IIIF content"""
        response = client.get(document.get_absolute_url())
        assertContains(
            response,
            f'<div id="iiif_viewer" data-iiif-urls="https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586"></div>',
            html=True,
        )

    def test_no_viewer(self, client, document):
        """Document with no IIIF shouldn't include viewer in template"""
        # remove fragment IIIF url
        fragment = document.fragments.first()
        fragment.iiif_url = ""
        fragment.save()
        response = client.get(document.get_absolute_url())
        assertNotContains(response, '<div class="wrapper">')

    def test_multi_viewer(self, client, join):
        """Document with many IIIF urls should add all to viewer in template"""
        response = client.get(join.get_absolute_url())
        first_url = join.textblock_set.first().fragment.iiif_url
        second_url = join.textblock_set.last().fragment.iiif_url
        assertContains(response, f'data-iiif-urls="{first_url} {second_url}"')

    def test_edit_link(self, client, admin_client, document):
        """Edit link should appear if user is admin, otherwise it should not"""
        edit_url = reverse("admin:corpus_document_change", args=[document.id])
        response = client.get(document.get_absolute_url())
        assertNotContains(response, edit_url)
        response = admin_client.get(document.get_absolute_url())
        assertContains(response, edit_url)


class TestDocumentScholarshipTemplate:
    def test_source_title(self, client, document, source):
        """Document scholarship template should show source titles if present"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response, '<span class="title">A Nice Cup of Tea</span>', html=True
        )
        source.title = ""
        source.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, '<span class="title">')

    def test_source_authors(self, client, document, twoauthor_source):
        """Document scholarship template should show source authors if present"""
        Footnote.objects.create(content_object=document, source=twoauthor_source)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response,
            '<span class="author">Kernighan, Brian; Ritchie, Dennis</span>',
            html=True,
        )
        for author in twoauthor_source.authors.all():
            twoauthor_source.authors.remove(author)
        twoauthor_source.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, '<span class="author">')

    def test_source_date(self, client, document, article):
        """Document scholarship template should show source pub. year if present"""
        Footnote.objects.create(content_object=document, source=article)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, '<span class="year">1963</span>', html=True)
        article.year = None
        article.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, '<span class="year">')

    def test_source_location(self, client, document, source):
        """Document scholarship template should show footnote location if present"""
        fn = Footnote.objects.create(
            content_object=document, source=source, location="p. 25"
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, '<span class="location">p. 25</span>', html=True)
        fn.location = ""
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, '<span class="location">')

    def test_source_url(self, client, document, article):
        """Document scholarship template should show source URL if present"""
        fn = Footnote.objects.create(
            content_object=document, source=article, url="https://example.com/"
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response, '<a href="https://example.com/">Link to source</a>', html=True
        )
        fn.url = ""
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertNotContains(response, '<a href="https://example.com/">')

    def test_source_relation(self, client, document, source):
        """Document scholarship template should show source relation to doc"""
        fn = Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.EDITION
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, '<span class="relation">Edition</span>', html=True)
        fn.doc_relation = [Footnote.EDITION, Footnote.TRANSLATION]
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response, '<span class="relation">Edition, Translation</span>', html=True
        )


class TestDocumentTabsSnippet:
    def test_detail_link(self, client, document):
        """document nav tabs should always include doc detail page link"""
        response = client.get(document.get_absolute_url())
        assertContains(response, document.get_absolute_url())

    def test_no_footnotes(self, client, document):
        """document nav should render inert scholarship tab if no footnotes"""
        response = client.get(document.get_absolute_url())
        # uses span, not link
        assertContains(response, "<span>Scholarship Records (0)</span>", html=True)

    def test_with_footnotes(self, client, document, source):
        """document nav should render scholarship link with footnote counter"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(document.get_absolute_url())

        # renders link to scholarship records page
        assertContains(
            response, reverse("corpus:document-scholarship", args=[document.pk])
        )
        # count should be 1
        assertContains(response, "Scholarship Records (1)")

        Footnote.objects.create(content_object=document, source=source)
        response = client.get(document.get_absolute_url())

        # count should be 2
        assertContains(response, "Scholarship Records (2)")

    def test_no_links(self, client, document, fragment):
        """document nav should render inert links tab if no external links"""
        # remove default URL from fragment
        fragment.url = ""
        fragment.save()
        response = client.get(document.get_absolute_url())

        # uses span, not link
        assertContains(response, "<span>External Links (0)</span>", html=True)

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

        # template currently has truncate chars 75; just check that the beginning
        # of the transcription is there
        rendered = self.template.render(context)
        assert transcription_txt[:75] in rendered
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
        assert (
            '<a name="previous page" title="previous page" class="disabled">' in result
        )
        assert '<a title="page 1" class="active"' in result
        assert '<a name="next page" title="next page" class="disabled">' in result

    def test_first_of_twenty_pages(self):
        paginator = Paginator(range(20), per_page=1)
        ctx = {"page_obj": paginator.page(1), "request": HttpRequest()}
        result = self.template.render(ctx)
        assert (
            '<a name="previous page" title="previous page" class="disabled">' in result
        )
        assert '<a title="page 1" class="active"' in result
        assert '<a title="page 2" href="?page=2">' in result
        assert (
            '<a name="next page" title="next page" rel="next" href="?page=2">' in result
        )

    def test_tenth_of_twenty_pages(self):
        paginator = Paginator(range(20), per_page=1)
        ctx = {"page_obj": paginator.page(10), "request": HttpRequest()}
        result = self.template.render(ctx)
        assert (
            '<a name="previous page" title="previous page" rel="prev" href="?page=9">'
            in result
        )
        assert '<a title="page 10" class="active"' in result
        assert '<a title="page 11" href="?page=11">' in result
        assert (
            '<a name="next page" title="next page" rel="next" href="?page=11">'
            in result
        )

    def test_with_query_param(self):
        paginator = Paginator(range(20), per_page=1)
        req = HttpRequest()
        req.GET = QueryDict("?q=contract")
        ctx = {"page_obj": paginator.page(10), "request": req}
        result = self.template.render(ctx)
        assert f"q=contract&page=9" in html.unescape(result)
