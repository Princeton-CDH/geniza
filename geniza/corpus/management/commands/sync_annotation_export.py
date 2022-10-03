from django.conf import settings
from django.core.management.base import BaseCommand

from geniza.corpus.annotation_export import AnnotationExporter


class Command(BaseCommand):
    """Synchronize annotation backup data with GitHub"""

    def handle(self, *args, **options):
        if not getattr(settings, "ANNOTATION_BACKUP_PATH"):
            raise CommandError(
                "Please configure ANNOTATION_BACKUP_PATH in django settings"
            )

        anno_exporter = AnnotationExporter(
            stdout=self.stdout, verbosity=options["verbosity"]
        )
        # set up repo object (pulls any changes)
        anno_exporter.setup_repo()
        # push changes
        anno_exporter.sync_github()
