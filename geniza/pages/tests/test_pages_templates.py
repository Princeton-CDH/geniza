import pytest
from pytest_django.asserts import assertContains
from wagtail.core.models import Page
from wagtail.core.models.sites import Site
from wagtail.tests.utils import WagtailPageTests

from geniza.pages.models import Contributor, CreditsPage, HomePage


class TestCreditsTemplate(WagtailPageTests):
    @pytest.mark.django_db
    def test_credits_contributors(self):
        """Credits page should list contributors"""

        # Setup home page and credit page
        default_site = Site.objects.get(is_default_site=True)
        home_page = HomePage(
            title="Home",
            description="Home page",
        )
        credits_page = CreditsPage(
            title="Credits",
            description="Test credits page",
            live=True,
        )
        root = Page.get_first_root_node()
        root.add_child(instance=home_page)
        home_page.add_child(instance=credits_page)
        default_site.root_page = home_page
        default_site.save()

        # Create contributors
        Contributor.objects.create(
            first_name="Marina", last_name="Rustow", role="Director"
        )
        Contributor.objects.create(
            first_name="Rachel", last_name="Richman", role="Project Manager"
        )

        # Response should use credits_page template and contain names and roles of contributors
        response = self.client.get("/en/credits/")
        self.assertTemplateUsed(response, template_name="pages/credits_page.html")
        assertContains(response, "<dt>Director</dt>", html=True)
        assertContains(response, "<dd>Marina Rustow</dd>", html=True)
        assertContains(response, "<dt>Project Manager</dt>", html=True)
        assertContains(response, "<dd>Rachel Richman</dd>", html=True)
