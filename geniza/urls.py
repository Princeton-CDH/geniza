"""geniza URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls import url
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.urls.conf import re_path
from django.views.generic.base import RedirectView, TemplateView
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps import Sitemap as WagtailSitemap
from wagtail.contrib.sitemaps import views as sitemap_views
from wagtail.core import urls as wagtail_urls

from geniza.corpus.sitemaps import DocumentScholarshipSitemap, DocumentSitemap

SITEMAPS = {
    "pages": WagtailSitemap,
    "document-detail": DocumentSitemap,
    "document-scholarship": DocumentScholarshipSitemap,
}

urlpatterns = [
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    # redirect homepage to admin site for now
    path("admin/", admin.site.urls),
    path("accounts/", include("pucas.cas_urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("taggit/", include("taggit_selectize.urls")),
    # NOTE: Sitemap most occur before wagtail urls
    url(
        "sitemap.xml",
        sitemap_views.index,
        {"sitemaps": SITEMAPS},
        name="sitemap-index",
    ),
    url(
        r"^sitemap-(?P<section>.+)\.xml$",
        sitemap_views.sitemap,
        {"sitemaps": SITEMAPS},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("cms/", include(wagtailadmin_urls)),
]

# urls that should be available in multiple languages
urlpatterns += i18n_patterns(
    path("", include("geniza.corpus.urls", namespace="corpus")),
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
