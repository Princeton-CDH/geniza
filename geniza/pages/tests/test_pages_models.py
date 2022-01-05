import pytest
from django.http.request import HttpRequest
from django.http.response import HttpResponseRedirect
from wagtail.core.models import Page
from wagtail.core.models.sites import Site

from geniza.pages.models import ContentPage, HomePage, SubMenuPage


class TestContentPage:
    @pytest.mark.django_db
    def test_get_context(self):
        content_page = ContentPage()
        assert content_page.get_context(HttpRequest())["page_type"] == "content-page"


class TestSubMenuPage:
    @pytest.mark.django_db
    def test_serve(self, client):
        # basic wagtail setup
        home_page = HomePage(title="Home page")
        root = Page.get_first_root_node()
        root.add_child(instance=home_page)
        sub_menu_page = SubMenuPage(title="Sub menu")
        home_page.add_child(instance=sub_menu_page)
        default_site = Site.objects.get(is_default_site=True)
        default_site.root_page = home_page
        default_site.save()

        # test GET request to initiate serve() functionality
        response = client.get(sub_menu_page.get_url())

        # sub_menu_page should redirect to home_page (its parent)
        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == 302
        assert response.url == home_page.get_url()

    @pytest.mark.django_db
    def test_show_in_menus(self):
        sub_menu_page = SubMenuPage()
        # should set show_in_menus to True by default
        assert sub_menu_page.show_in_menus == True
