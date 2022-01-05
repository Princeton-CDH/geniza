from datetime import date

from django.urls import reverse

from geniza.corpus.models import Document
from geniza.corpus.sitemaps import (
    DocumentScholarshipSitemap,
    DocumentSitemap,
    solr_timestamp_to_date,
)
from geniza.footnotes.models import Footnote


def test_solr_timestamp_to_date():
    assert solr_timestamp_to_date("2020-05-12T15:46:20.341Z") == date(2020, 5, 12)


class TestDocumentSitemap:
    def test_items(self, document):
        # Ensure that documents are supressed if they aren't public
        assert document.status == Document.PUBLIC
        sitemap = DocumentSitemap()
        assert document.id in [obj["id"] for obj in sitemap.items()]

        document.status = Document.SUPPRESSED
        document.save()
        sitemap = DocumentSitemap()
        assert len(sitemap.items()) == 0

    def test_lastmod(self, document):
        sitemap = DocumentScholarshipSitemap()
        assert sitemap.lastmod(document) == document.last_modified


class TestDocumentScholarshipSitemap:
    def test_items(self, document, source):
        # Ensure that only documents with footnotes are returned
        assert document.footnotes.count() == 0
        sitemap = DocumentScholarshipSitemap()
        assert len(sitemap.items()) == 0

        footnote = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )
        sitemap = DocumentScholarshipSitemap()
        assert document.id in [obj["id"] for obj in sitemap.items()]

        # Ensure that documents are supressed if they aren't public
        document.status = Document.SUPPRESSED
        document.save()
        sitemap = DocumentScholarshipSitemap()
        assert len(sitemap.items()) == 0

    def test_location(self, document, source):
        footnote = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )
        document.save()
        sitemap = DocumentScholarshipSitemap()
        assert sitemap.location(document) == reverse(
            "corpus:document-scholarship", args=[document.id]
        )
        assert sitemap.location(document) == "/en/documents/3951/scholarship/"

    def test_lastmod(self, document, source):
        footnote = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )
        sitemap = DocumentScholarshipSitemap()
        assert sitemap.lastmod(document) == document.last_modified
