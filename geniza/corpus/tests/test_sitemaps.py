from datetime import date
from unittest.mock import patch

from django.urls import reverse
from parasolr.django import SolrClient

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
    def test_items(self, document, suppressed_document):
        # Ensure that documents are supressed if they aren't public
        assert document.status == Document.PUBLIC
        SolrClient().update.index(
            [
                document.index_data(),  # no scholarship records
                suppressed_document.index_data(),  # suppressed
            ],
            commit=True,
        )
        sitemap = DocumentSitemap()
        assert document.id in [obj["pgpid"] for obj in sitemap.items()]
        assert suppressed_document.id not in [obj["pgpid"] for obj in sitemap.items()]

    def test_location(self):
        assert DocumentSitemap().location(
            {"pgpid": "444", "last_modified": "2020-05-12T15:46:20.341Z"}
        ) == reverse("corpus:document", args=["444"])

    def test_lastmod(self):
        assert DocumentSitemap().lastmod(
            {"last_modified": "2020-05-12T15:46:20.341Z"}
        ) == date(2020, 5, 12)


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
        assert document in sitemap.items()

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
