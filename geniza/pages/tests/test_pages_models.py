import pytest
from django.http.request import HttpRequest

from geniza.pages.models import ContentPage, Contributor, CreditsPage


class TestContentPage:
    @pytest.mark.django_db
    def test_get_context(self):
        content_page = ContentPage()
        assert content_page.get_context(HttpRequest())["page_type"] == "content-page"


class TestCreditsPage:
    @pytest.mark.django_db
    def test_contributors(self):
        credits_page = CreditsPage()
        marina = Contributor.objects.create(
            first_name="Marina", last_name="Rustow", role="Director"
        )
        rachel = Contributor.objects.create(
            first_name="Rachel", last_name="Richman", role="Project Manager"
        )
        credit_pks = [cont.pk for cont in credits_page.contributors()]
        assert marina.pk in credit_pks
        assert rachel.pk in credit_pks


class TestContributor:
    def test_natural_key(self):
        marina = Contributor(first_name="Marina", last_name="Rustow", role="Director")
        assert marina.natural_key() == ("Rustow", "Marina")

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        marina = Contributor.objects.create(
            first_name="Marina", last_name="Rustow", role="Director"
        )
        assert Contributor.objects.get_by_natural_key("Rustow", "Marina") == marina

    def test_str(self):
        marina = Contributor(first_name="Marina", last_name="Rustow", role="Director")
        assert str(marina) == "Marina Rustow"

        # no firstname
        assert str(Contributor(last_name="Goitein")) == "Goitein"
