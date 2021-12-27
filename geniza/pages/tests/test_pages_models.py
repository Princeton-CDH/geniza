import pytest
from django.http.request import HttpRequest

from geniza.pages.models import ContentPage


class TestContentPage:
    @pytest.mark.django_db
    def test_get_context(self):
        content_page = ContentPage()
        assert content_page.get_context(HttpRequest())["page_type"] == "content-page"
