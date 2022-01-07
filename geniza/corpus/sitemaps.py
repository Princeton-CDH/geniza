from datetime import date

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from parasolr.utils import solr_timestamp_to_datetime

from geniza.corpus.models import Document
from geniza.corpus.solr_queryset import DocumentSolrQuerySet


class DocumentSitemap(Sitemap):
    url_name = "corpus:document"
    i18n = True

    def get_queryset(self):
        return DocumentSolrQuerySet().filter(status=Document.PUBLIC_LABEL)

    def items(self):
        return (
            self.get_queryset()
            .only("last_modified", "pgpid")
            .get_results(
                rows=100_000
            )  # Solr defaults to a low number of rows, ask for effectively all of them.
        )

    def lastmod(self, obj):
        return solr_timestamp_to_datetime(obj["last_modified"]).date()

    def location(self, obj):
        return reverse(self.url_name, args=[obj["pgpid"]])


class DocumentScholarshipSitemap(DocumentSitemap):
    url_name = "corpus:document-scholarship"

    def get_queryset(self):
        # Only return documents with footnotes. A document scholarship page returns
        #  a 404 if there are no footnotes.
        return super().get_queryset().filter(scholarship_count__range=(1, None))
