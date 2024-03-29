from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand


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

        # set up test models via JSON fixtures
        call_command("loaddata", "ui_ux_test_documents.json")

        # index everything in solr
        call_command("index")
