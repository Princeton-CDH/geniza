import pytest
from django.http.request import HttpRequest

from geniza.pages.models import ContentPage, HomePage


class TestHomePage:
    @pytest.mark.django_db
    def test_get_context(self):
        home_page = HomePage()
        assert home_page.get_context(HttpRequest())["page_type"] == "homepage"


class TestContentPage:
    @pytest.mark.django_db
    def test_get_context(self):
        content_page = ContentPage()
        assert content_page.get_context(HttpRequest())["page_type"] == "content-page"
