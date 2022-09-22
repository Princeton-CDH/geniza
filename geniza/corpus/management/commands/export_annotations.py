import json
import os
from collections import defaultdict
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from django.template.loader import get_template
from django.utils.text import slugify
from git import InvalidGitRepositoryError, Repo

from geniza.annotations.models import Annotation, annotations_to_list
from geniza.corpus.annotation_export import AnnotationExporter
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote


class Command(BaseCommand):
    """Backup annotation data and synchronize to GitHub"""

    def add_arguments(self, parser):
        parser.add_argument(
            "pgpids", nargs="*", help="Export the specified documents only"
        )

    def handle(self, *args, **options):
        if not getattr(settings, "ANNOTATION_BACKUP_PATH"):
            raise CommandError(
                "Please configure ANNOTATION_BACKUP_PATH in django settings"
            )

        anno_exporter = AnnotationExporter(
            pgpids=options["pgpids"], stdout=self.stdout, verbosity=options["verbosity"]
        ).export()
