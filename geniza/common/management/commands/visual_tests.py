from django.core.management import call_command
from django.core.management.base import BaseCommand
from percy import percy_snapshot
from selenium import webdriver
from selenium.webdriver.common.keys import Keys


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

        # content page
        browser.get("http://localhost:8000/en/content/")
        percy_snapshot(browser, "Content Page")
        # dark mode version
        browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        percy_snapshot(browser, "Content Page (dark mode)")

        # document search with document type filter expanded
        # NOTE: revise to capture search filter panel when we implement it
        browser.get("http://localhost:8000/en/documents/")
        # open document type filter
        browser.find_element_by_css_selector(".doctype-filter summary").click()
        # click the first option
        browser.find_element_by_css_selector(
            ".doctype-filter li:nth-child(1) label"
        ).click()
        percy_snapshot(browser, "Document Search filter")
        # dark mode version
        browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        percy_snapshot(browser, "Document Search filter (dark mode)")

        # document search
        browser.get(
            "http://localhost:8000/en/documents/?q=the+writer+Avraham+באנפנא&per_page=2"
        )
        percy_snapshot(browser, "Document Search")
        # dark mode version
        browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        percy_snapshot(browser, "Document Search (dark mode)")

        # document detail
        browser.get("http://localhost:8000/en/documents/2532/")
        percy_snapshot(browser, "Document Details")
        # dark mode version
        browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        percy_snapshot(browser, "Document Details (dark mode)")

        # document scholarship
        browser.get("http://localhost:8000/en/documents/9469/scholarship/")
        percy_snapshot(browser, "Document Scholarship Records")
        # dark mode version
        browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        percy_snapshot(browser, "Document Scholarship Records (dark mode)")

        # mobile menu
        browser.get("http://localhost:8000/en/documents/2532/#menu")
        mobile_menu_css = "ul#menu { left: 0 !important; transition: none !important; }"
        percy_snapshot(browser, "Mobile menu", percy_css=mobile_menu_css)
        # dark mode version
        browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        percy_snapshot(browser, "Mobile menu (dark mode)", percy_css=mobile_menu_css)

        # about submenu open on both desktop and mobile
        browser.get("http://localhost:8000/en/documents/2532/#menu")
        # open about menu
        browser.find_element_by_id("open-about-menu").send_keys(Keys.ENTER)
        about_menu_css = "ul#about-menu { left: 0 !important; transition: none !important; } @media (min-width: 900px) { ul#about-menu { left: auto !important; } }"
        percy_snapshot(browser, "About submenu", percy_css=about_menu_css)
        # dark mode version
        browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        percy_snapshot(browser, "About submenu (dark mode)", percy_css=about_menu_css)

        # 404 page TODO
        # browser.get("http://localhost:8000/bad-url")
        # percy_snapshot(browser, "404 Page")
        # dark mode version
        # browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        # percy_snapshot(browser, "404 Page (dark mode)")

        # 500 page TODO
        # browser.get("http://localhost:8000/500")
        # percy_snapshot(browser, "500 Page")
        # dark mode version
        # browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
        # percy_snapshot(browser, "500 Page (dark mode)")

    def handle(self, *args, **options):
        # spin up browser and take snapshots; shut down when finished
        browser = self.get_browser()
        self.take_snapshots(browser)
        browser.quit()
