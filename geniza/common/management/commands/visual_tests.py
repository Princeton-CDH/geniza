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

    def take_snapshots(self, browser, dark_mode=False):
        """Take DOM snapshots of a set of URLs and upload to Percy."""

        dark_mode_str = ""  # empty string in light mode

        # dark mode switch
        browser.get("http://localhost:8000/")
        if dark_mode:
            # turn on dark mode, save in local storage
            browser.find_element_by_css_selector("#theme-toggle").send_keys(Keys.ENTER)
            dark_mode_str = " (dark mode)"

        # homepage
        browser.get("http://localhost:8000/")
        percy_snapshot(browser, "Home%s" % dark_mode_str)

        # content page
        browser.get("http://localhost:8000/en/content/")
        percy_snapshot(browser, "Content Page%s" % dark_mode_str)

        # document search with document type filter expanded
        browser.get("http://localhost:8000/en/documents/?per_page=2#filters")
        # open document type filter
        browser.find_element_by_css_selector(".doctype-filter summary").click()
        # click the first option
        browser.find_element_by_css_selector(
            ".doctype-filter li:nth-child(1) label"
        ).click()
        filter_modal_css = "fieldset#filters { display: flex !important; }"
        percy_snapshot(
            browser,
            "Document Search filter%s" % dark_mode_str,
            percy_css=filter_modal_css,
        )

        # document search
        browser.get(
            "http://localhost:8000/en/documents/?q=the+writer+Avraham+באנפנא&per_page=2"
        )
        percy_snapshot(browser, "Document Search%s" % dark_mode_str)

        # document detail
        browser.get("http://localhost:8000/en/documents/8151/")
        percy_snapshot(browser, "Document Details%s" % dark_mode_str)

        # document scholarship
        browser.get("http://localhost:8000/en/documents/9469/scholarship/")
        percy_snapshot(browser, "Document Scholarship Records%s" % dark_mode_str)

        # mobile menu
        browser.get("http://localhost:8000/en/documents/9469/#menu")
        # custom CSS to ensure that on mobile, the menu transition is disabled and the menu
        # is in the correct position
        mobile_menu_css = "ul#menu { left: 0 !important; transition: none !important; }"
        percy_snapshot(
            browser, "Mobile menu%s" % dark_mode_str, percy_css=mobile_menu_css
        )

        # about submenu open on both desktop and mobile
        browser.get("http://localhost:8000/en/documents/8151/#menu")
        # open about menu
        browser.find_element_by_id("open-about-menu").send_keys(Keys.ENTER)
        # custom CSS to ensure that on mobile, the about menu transition is disabled and the menu
        # is in the correct position; and that on desktop, that override does not impact its position
        about_menu_css = "ul#about-menu { left: 0 !important; transition: none !important; } @media (min-width: 900px) { ul#about-menu { left: auto !important; } }"
        percy_snapshot(
            browser, "About submenu%s" % dark_mode_str, percy_css=about_menu_css
        )

        # 404 page
        browser.get("http://localhost:8000/en/bad-url/")
        percy_snapshot(browser, "404 Page%s" % dark_mode_str)

        # 500 page
        browser.get("http://localhost:8000/_500/")
        percy_snapshot(browser, "500 Page%s" % dark_mode_str)

    def handle(self, *args, **options):
        # spin up browser and take snapshots; shut down when finished
        browser = self.get_browser()
        # light mode
        self.take_snapshots(browser)
        # dark mode
        self.take_snapshots(browser, dark_mode=True)
        browser.quit()
