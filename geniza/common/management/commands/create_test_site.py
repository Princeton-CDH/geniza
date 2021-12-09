from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand
from wagtail.core.models.sites import Site as WagatilSite


class Command(BaseCommand):
    def handle(self, *args, **options):
        """Fill the database with models to approximate a real site."""
        # NOTE not idempotent! running more than once will duplicate models.

        # set default django site (not wagtail site) domain so sitemaps work
        django_site = Site.objects.get()
        django_site.domain = "localhost:8000"
        django_site.save()

        # set up fake content
        call_command("bootstrap_content", "-f")

        # set wagtail site port so page URL reversing works
        wagtail_site = WagatilSite.objects.get(is_default_site=True)
        wagtail_site.port = 8000
        wagtail_site.save()

        # set up test models via JSON fixtures
        call_command("loaddata", "ui_ux_test_documents.json")

        # index everything in solr
        call_command("index")
