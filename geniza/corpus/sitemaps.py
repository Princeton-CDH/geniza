from datetime import date

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from parasolr.utils import solr_timestamp_to_datetime

from geniza.corpus.models import Document
from geniza.corpus.solr_queryset import DocumentSolrQuerySet


class DocumentSitemap(Sitemap):
    def items(self):
        return (
            DocumentSolrQuerySet()
            .filter(status=Document.PUBLIC_LABEL)
            .only("last_modified", "pgpid")
        )

    def lastmod(self, obj):
        return solr_timestamp_to_datetime(obj["last_modified"]).date()

    def location(self, obj):
        return reverse("corpus:document", args=[obj["pgpid"]])


class DocumentScholarshipSitemap(Sitemap):
    def items(self):
        # Only return documents with footnotes. A document scholarship page returns
        #  a 404 if there are no footnotes.
        return (
            DocumentSolrQuerySet()
            .filter(status="Public", scholarship_count__range=(1, None))
            .only("pgpid", "last_modified")
        )

    def location(self, obj):
        return reverse("corpus:document-scholarship", args=[obj["pgpid"]])

    def lastmod(self, obj):
        return solr_timestamp_to_datetime(obj["last_modified"]).date()
