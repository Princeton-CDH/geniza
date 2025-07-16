import pytest
from django.http.request import HttpRequest
from django.http.response import HttpResponseRedirect
from wagtail.models import Page
from wagtail.models.sites import Site

from geniza.pages.models import ContainerPage, ContentPage, HomePage


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


class TestContainerPage:
    @pytest.mark.django_db
    def test_serve(self, client):
        # basic wagtail setup
        home_page = HomePage(title="Home page")
        root = Page.get_first_root_node()
        root.add_child(instance=home_page)
        container_page = ContainerPage(title="Container")
        home_page.add_child(instance=container_page)
        default_site = Site.objects.get(is_default_site=True)
        default_site.root_page = home_page
        default_site.save()

        # test GET request to initiate serve() functionality
        response = client.get(container_page.get_url())

        # container_page should redirect to home_page (its parent)
        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == 302
        assert response.url == home_page.get_url()

    @pytest.mark.django_db
    def test_show_in_menus(self):
        container_page = ContainerPage()
        # should set show_in_menus to True by default
        assert container_page.show_in_menus == True
