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
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.urls.conf import re_path
from django.views.generic.base import RedirectView
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.core import urls as wagtail_urls

urlpatterns = [
    # redirect homepage to admin site for now
    path("admin/", admin.site.urls),
    path("accounts/", include("pucas.cas_urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("taggit/", include("taggit_selectize.urls")),
    path("cms/", include(wagtailadmin_urls)),
]

# urls that should be available in multiple languages
urlpatterns += i18n_patterns(
    path("", include("geniza.corpus.urls", namespace="corpus")),
    path("", include(wagtail_urls)),
)

# Media URLs for wagtail
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns.append(
            path("__debug__/", include(debug_toolbar.urls)),
        )
    except ImportError:
        pass
