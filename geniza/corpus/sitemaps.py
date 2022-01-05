from datetime import date

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from geniza.corpus.models import Document
from geniza.corpus.solr_queryset import DocumentSolrQuerySet


def solr_timestamp_to_date(timestamp):
    """Convert solr isoformat date time string to python date."""
    # format: 2020-05-12T15:46:20.341Z
    # django sitemap only includes date, so strip off time
    yearmonthday = timestamp.split("T")[0]
    return date(*[int(val) for val in yearmonthday.split("-")])


class DocumentSitemap(Sitemap):
    def items(self):
        return (
            DocumentSolrQuerySet()
            .filter(
                status="Public"
            )  # ?: It's not saved as "Document.PUBLIC" which is "P"
            .only("last_modified", "pgpid", "slug")
        )

    def lastmod(self, obj):
        return solr_timestamp_to_date(obj["last_modified"])

    def location(self, obj):
        return reverse("corpus:document", args=[obj["pgpid"]])


class DocumentScholarshipSitemap(Sitemap):
    def items(self):
        # Only return documents with footnotes. A document scholarship page returns
        #  a 404 if there are no footnotes.
        return (
            DocumentSolrQuerySet()
            .filter(status="Public", footnotes__isnull=False)
            .only("pgpid", "last_modified")
        )

    def location(self, obj):
        return reverse("corpus:document-scholarship", args=[obj["pgpid"]])

    def lastmod(self, obj):
        return solr_timestamp_to_date(obj["last_modified"])
