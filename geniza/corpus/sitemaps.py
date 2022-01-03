from datetime import date

from django.contrib.sitemaps import Sitemap
from django.db.models import F

from geniza.corpus.models import Document


class DocumentSitemap(Sitemap):
    def items(self):
        return Document.objects.filter(status=Document.PUBLIC)


class DocumentScholarshipSitemap(Sitemap):
    def items(self):
        return Document.objects.filter(status=Document.PUBLIC, footnotes__isnull=False)

    def location(self, obj):
        return obj.get_absolute_url() + "scholarship/"


"""
https://docs.djangoproject.com/en/4.0/ref/contrib/sitemaps/#django.contrib.sitemaps.Sitemap.paginator

paginator¶

    Optional.

    This property returns a Paginator for items(). If you generate sitemaps in a batch you may want to override this as a cached property in order to avoid multiple items() calls.

"""
