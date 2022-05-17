from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from parasolr.utils import solr_timestamp_to_datetime

from geniza.corpus.models import Document
from geniza.corpus.solr_queryset import DocumentSolrQuerySet


class DocumentSitemap(Sitemap):
    """Sitemap for individual document pages"""

    url_name = "corpus:document"
    i18n = True
    alternates = True

    def get_queryset(self):
        return (
            DocumentSolrQuerySet()
            .filter(status=Document.PUBLIC_LABEL)
            .only("last_modified", "pgpid")
            .order_by("pgpid")
        )

    _cache_items = None

    def items(self):
        # django sitemap requests items multiple times; cache the queryset result
        # so we only hit solr once per request
        if self._cache_items is None:
            self._cache_items = self.get_queryset().get_results(rows=100_000)
            # by default Solr only returns 10 rows; django paginates sitemaps at 50k items;
            # ensure we get all rows

        return self._cache_items

    def lastmod(self, obj):
        return solr_timestamp_to_datetime(obj["last_modified"]).date()

    def location(self, obj):
        return reverse(self.url_name, kwargs={"pk": obj["pgpid"]})


class DocumentScholarshipSitemap(DocumentSitemap):
    """Sitemap for individual document scholarship records pages"""

    url_name = "corpus:document-scholarship"

    def get_queryset(self):
        # Limit to documents with scholarship records; document scholarship
        # page does not exist for pages without scholarship records.
        return super().get_queryset().filter(scholarship_count__range=(1, None))
