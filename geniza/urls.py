"""geniza URL Configuration
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView, TemplateView
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps import Sitemap as WagtailSitemap
from wagtail.contrib.sitemaps import views as sitemap_views
from wagtail.core import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from geniza.corpus.sitemaps import DocumentScholarshipSitemap, DocumentSitemap

SITEMAPS = {
    "pages": WagtailSitemap,
    "documents": DocumentSitemap,
    "document-scholarship": DocumentScholarshipSitemap,
}

urlpatterns = [
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/img/icons/favicon.ico", permanent=True),
    ),
    # redirect homepage to admin site for now
    path("admin/", admin.site.urls),
    path("annotations/", include("geniza.annotations.urls", namespace="annotations")),
    path("accounts/", include("pucas.cas_urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("taggit/", include("taggit_selectize.urls")),
    re_path(
        "sitemap.xml",
        sitemap_views.index,
        {"sitemaps": SITEMAPS},
        name="sitemap-index",
    ),
    re_path(
        r"^sitemap-(?P<section>.+)\.xml$",
        sitemap_views.sitemap,
        {"sitemaps": SITEMAPS},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("cms/", include(wagtailadmin_urls)),
    path("", include("geniza.corpus.uris", namespace="corpus-uris")),
    path("documents/", include(wagtaildocs_urls)),
    path("_500/", lambda _: 1 / 0),
]

# urls that should be available in multiple languages
urlpatterns += i18n_patterns(
    path("", include("geniza.corpus.urls", namespace="corpus")),
    path("", include("geniza.entities.urls", namespace="entities")),
    path("", include(wagtail_urls)),
)

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns.append(
            path("__debug__/", include(debug_toolbar.urls)),
        )
    except ImportError:
        pass

    # Media URLs for wagtail
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
