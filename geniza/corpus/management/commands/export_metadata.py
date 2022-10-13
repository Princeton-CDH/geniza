import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from geniza.corpus.metadata_export import DocumentExporter


class Command(BaseCommand):
    def print(self, *x, **y):
        """
        A stdout-friendly method of printing for manage.py commands
        """
        self.stdout.write(" ".join(str(xx) for xx in x), ending="\n", **y)

    def add_arguments(self, parser):
        ofn = f'pgp_documents-{timezone.now().strftime("%Y%m%dT%H%M%S")}.csv'
        parser.add_argument(
            "-o", "--output_filename", type=str, default=ofn, required=False
        )

    def handle(self, *args, **options):
        began = time.time()
        ofn = options["output_filename"]
        self.print(f"Exporting data as CSV to: {ofn}")

        exporter = DocumentExporter(progress=True)
        exporter.write_export_data_csv(fn=ofn)

        self.print(f"Finished CSV export in {time.time()-began:.1f} seconds")
