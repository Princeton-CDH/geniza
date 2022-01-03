from geniza.corpus.models import Document
from geniza.corpus.sitemaps import DocumentScholarshipSitemap, DocumentSitemap


class TestDocumentSitemap:
    def test_items(self, document):
        # Ensure that documents are supressed if they aren't public
        assert document.status == Document.PUBLIC
        sitemap = DocumentSitemap()
        assert len(sitemap.items()) == 1

        document.status = Document.SUPPRESSED
        document.save()
        sitemap = DocumentSitemap()
        assert len(sitemap.items()) == 0


class TestDocumentScholarshipSitemap:
    def test_items(self, document, footnote):
        # Ensure that documents are supressed if they aren't public
        document.status = Document.SUPPRESSED
        document.save()
        sitemap = DocumentScholarshipSitemap()
        assert len(sitemap.items()) == 0

        # Ensure that only documents with footnotes are returned
        document.status = Document.PUBLIC
        document.save()
        sitemap = DocumentScholarshipSitemap()
        assert len(sitemap.items()) == 1

        document.footnotes.all().delete()
        sitemap = DocumentScholarshipSitemap()
        assert len(sitemap.items()) == 0

    def test_location(self, document, footnote):
        document.footnotes.add(footnote)
        document.save()
        sitemap = DocumentScholarshipSitemap()
        assert sitemap.location(sitemap.items()[0]).endswith("scholarship/")
