from django.contrib.sitemaps import Sitemap

from geniza.corpus.models import Document


class DocumentSitemap(Sitemap):
    def items(self):
        return Document.objects.filter(status=Document.PUBLIC)

    def lastmod(self, obj):
        return obj.last_modified


class DocumentScholarshipSitemap(Sitemap):
    def items(self):
        return Document.objects.filter(status=Document.PUBLIC, footnotes__isnull=False)

    def location(self, obj):
        return obj.get_absolute_url() + "scholarship/"

    def lastmod(self, obj):
        return obj.last_modified
