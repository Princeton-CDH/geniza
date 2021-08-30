from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from geniza.corpus.models import TextBlock
from geniza.footnotes.models import Footnote


class TestDocumentDetailTemplate:
    def test_shelfmark(self, client, document):
        """Document detail template should include shelfmark"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "<dd>CUL Add.2586</dd>", html=True)

    def test_doctype(self, client, document):
        """Document detail template should include document type"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "<dd>Legal</dd>", html=True)

    def test_first_input(self, client, document):
        """Document detail template should include document first input date"""
        response = client.get(document.get_absolute_url())
        assertContains(response, "<dd>2004</dd>", html=True)

    def test_tags(self, client, document):
        """Document detail template should include all document tags"""
        response = client.get(document.get_absolute_url())
        assertContains(response, '<dd class="tag">#bill of sale</dd>', html=True)
        assertContains(response, '<dd class="tag">#real estate</dd>', html=True)

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
