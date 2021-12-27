import pytest
from django.http import Http404
from django.http.request import HttpRequest

from geniza.pages.models import AboutPage, ContentPage


class TestContentPage:
    @pytest.mark.django_db
    def test_get_context(self):
        content_page = ContentPage()
        assert content_page.get_context(HttpRequest())["page_type"] == "content-page"


class TestAboutPage:
    @pytest.mark.django_db
    def test_serve(self):
        about_page = AboutPage()
        with pytest.raises(Http404):
            about_page.serve(HttpRequest())
