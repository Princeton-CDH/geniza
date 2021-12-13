from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.templatetags.static import static
from wagtail.core.models import Page
from wagtail.core.models.i18n import Locale
from wagtail.core.models.sites import Site

from geniza.pages.models import ContentPage, CreditsPage, HomePage


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-H",
            "--hostname",
            default="localhost",
            help="hostname from which the app is served (default: localhost)",
        )
        parser.add_argument(
            "-p",
            "--port",
            default="8000",
            help="port from which the app is served (default: 8000)",
        )
        parser.add_argument(
            "-l",
            "--locale",
            default="en",
            help="language code for content pages (default: en)",
        )
        parser.add_argument(
            "-f",
            "--fixtures",
            action="store_true",
            help="include test fixture content page",
        )

    def handle(self, *args, **options):
        """Bootstrap content for Geniza public project site.
        NOTE: Not idempotent. Will recreate pages if they already exist."""

        include_fixtures = options.get("fixtures")
        hostname = options.get("hostname")
        port = options.get("port")
        language_code = options.get("locale")
        (locale, _) = Locale.objects.get_or_create(language_code=language_code)

        # Bootstrap empty home page
        home_page = HomePage(
            title="The Princeton Geniza Project",
            description="Home page",
            locale=locale,
        )
        root = Page.get_first_root_node()
        root.add_child(instance=home_page)

        # Create credits page
        credits_page = CreditsPage(
            title="Credits",
            slug="credits",
            description="List of Geniza Project contributors and their roles",
            locale=locale,
        )
        home_page.add_child(instance=credits_page)

        # Bootstrap other empty pages
        empty_pages = [
            ContentPage(
                title="Contact Us",
                slug="contact",
                description="Contact information",
                locale=locale,
            ),
            ContentPage(
                title="How to Cite",
                slug="how-to-cite",
                description="Instructions for citing the Princeton Geniza Project",
                locale=locale,
            ),
            ContentPage(
                title="Data Exports",
                slug="data-exports",
                description="Information about exporting data",
                locale=locale,
            ),
            ContentPage(
                title="Technical",
                slug="technical",
                description="Technical information",
                locale=locale,
            ),
            ContentPage(
                title="FAQ",
                slug="faq",
                description="Frequently asked questions",
                locale=locale,
            ),
        ]
        for page in empty_pages:
            home_page.add_child(instance=page)

        if include_fixtures:
            # Create test page
            test_content_page = self.generate_test_content_page()
            home_page.add_child(instance=test_content_page)

        # Create site or add page tree to site
        try:
            default_site = Site.objects.get(is_default_site=True)
            default_site.root_page = home_page
            default_site.save()
        except ObjectDoesNotExist:
            default_site = Site.objects.create(
                hostname=hostname,
                port=port,
                root_page=home_page,
                is_default_site=True,
                site_name="Geniza",
            )

    def generate_test_content_page(self):
        # Create test content page from fixture
        with open(
            "geniza/pages/fixtures/example_content_page.html", "r"
        ) as content_fixture:
            content = content_fixture.read()
        return ContentPage(
            title="Page Title",
            description="Example page",
            slug="content",
            body=content.replace(  # get static URLs for test images
                "test-image-fragment.jpg", static("test-image-fragment.jpg")
            ).replace("test-image-tagnetwork.png", static("test-image-tagnetwork.png")),
            live=True,
        )
