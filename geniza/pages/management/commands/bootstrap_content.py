from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import UploadedFile
from django.core.management.base import BaseCommand
from django.templatetags.static import static
from wagtail.images.models import Image
from wagtail.models import Page
from wagtail.models.i18n import Locale
from wagtail.models.sites import Site
from wagtail.rich_text import RichText

from geniza.pages.models import ContainerPage, ContentPage, HomePage


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
        (locale, _) = Locale.objects.get_or_create(language_code="en")

        # Bootstrap home page
        with open("geniza/pages/fixtures/example_homepage.html", "r") as home_fixture:
            home_content = home_fixture.read()

        home_page = HomePage(
            title="The Princeton Geniza Project",
            description="Home page",
            locale=locale,
            body=[("paragraph", RichText(home_content))],
            live=True,
        )

        # Add home page to root
        root = Page.get_first_root_node()
        root.add_child(instance=home_page)

        # Create container page called "About"
        container_page = ContainerPage(title="About", slug="about", locale=locale)
        home_page.add_child(instance=container_page)

        # Bootstrap other empty content pages

        # Pages for main navigation menu
        root_pages = [
            ContentPage(
                title="Contact Us",
                slug="contact",
                description="Contact information",
                locale=locale,
            ),
        ]
        for page in root_pages:
            page.show_in_menus = True
            home_page.add_child(instance=page)

        # Pages for About sub-navigation menu
        container_pages = [
            ContentPage(
                title="Credits",
                slug="credits",
                description="List of Geniza Project contributors and their roles",
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
        for page in container_pages:
            page.show_in_menus = True
            container_page.add_child(instance=page)

        if include_fixtures:
            # Create test page
            test_content_page = self.generate_test_content_page()
            home_page.add_child(instance=test_content_page)

        # Create or update site with page tree and other options
        try:
            default_site = Site.objects.get(is_default_site=True)
            default_site.root_page = home_page
            default_site.port = port
            default_site.hostname = hostname
            default_site.site_name = "Geniza"
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
        """Create a test content page from fixture"""
        with open(
            "geniza/pages/fixtures/example_content_page.html", "r"
        ) as content_fixture:
            paragraph_1 = content_fixture.read()
        image_caption = "Image Caption"
        image1 = Image(title="Fragment", width=400, height=535)
        with open("sitemedia/img/fixtures/test-image-fragment.jpg", "rb") as fragment:
            image1.file = UploadedFile(file=fragment)
            image1.save()
        paragraph2 = """<p>The metadata is stored in the backend in Google Sheets and pushed out to
            the PGP site every 24 hours. The transcriptions are stored in Bitbucket.</p>"""
        image2 = Image(title="Tag Network", width=557, height=313)
        with open(
            "sitemedia/img/fixtures/test-image-tagnetwork.png", "rb"
        ) as tag_network:
            image2.file = UploadedFile(file=tag_network)
            image2.save()
        paragraph3 = """<p>Previous versions of the PGP database were based on the TextGarden web
            application developed in 2005 by Rafael Alvarado, Manager of Humanities
            Computing Research Applications at Princeton, and the original browser
            developed by Peter Batke at Princeton in the late 1990s.</p>"""
        body = [
            ("paragraph", RichText(paragraph_1)),
            (
                "image",
                {
                    "image": image1,
                    "alternative_text": image_caption,
                    "caption": RichText(image_caption),
                },
            ),
            ("paragraph", RichText(paragraph2)),
            (
                "image",
                {
                    "image": image2,
                    "alternative_text": image_caption,
                    "caption": RichText(image_caption),
                },
            ),
            ("paragraph", RichText(paragraph3)),
        ]
        return ContentPage(
            title="Page Title",
            description="Example page",
            slug="content",
            body=body,
            live=True,
            show_in_menus=False,
        )
