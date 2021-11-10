from django.core.management import call_command
from django.core.management.base import BaseCommand
from percy import percy_snapshot
from selenium import webdriver


class Command(BaseCommand):
    """Execute visual regression tests against a running django server."""

    help = __doc__

    def get_browser(self):
        """Initialize a browser driver to use for taking snapshots."""
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--headless")
        return webdriver.Chrome(options=options)

    def take_snapshots(self, browser):
        """Take DOM snapshots of a set of URLs and upload to Percy."""

        # homepage TODO
        # browser.get("http://localhost:8000/")
        # percy_snapshot(browser, "Home")

        # content page TODO
        # browser.get("http://localhost:8000/content")
        # percy_snapshot(browser, "Content Page")

        # document search
        # search term should match descriptions of 3951 and the fake letter document
        browser.get("http://localhost:8000/documents/?q=tujib+description")
        percy_snapshot(browser, "Document Search")

        # document detail
        browser.get("http://localhost:8000/documents/999999/")
        percy_snapshot(browser, "Document Details")

        # # document scholarship
        browser.get("http://localhost:8000/documents/3951/")
        percy_snapshot(browser, "Document Scholarship Records")

        # 404 page TODO
        # browser.get("http://localhost:8000/bad-url")
        # percy_snapshot(browser, "404 Page")

        # 500 page TODO
        # browser.get("http://localhost:8000/500")
        # percy_snapshot(browser, "500 Page")

    def handle(self, *args, **options):
        # spin up browser and take snapshots; shut down when finished
        browser = self.get_browser()
        self.take_snapshots(browser)
        browser.quit()
