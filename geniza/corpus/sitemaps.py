from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from geniza.corpus.models import Document


class DocumentSitemap(Sitemap):
    def items(self):
        return Document.objects.filter(status=Document.PUBLIC)

    def lastmod(self, obj):
        return obj.last_modified


class DocumentScholarshipSitemap(Sitemap):
    def items(self):
        # Only return documents with footnotes. A document scholarship page returns
        #  a 404 if there are no footnotes.
        return Document.objects.filter(status=Document.PUBLIC, footnotes__isnull=False)

    def location(self, obj):
        return reverse("corpus:document-scholarship", args=[obj.id])

    def lastmod(self, obj):
        return obj.last_modified
