import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from geniza.corpus.csv_export import export_docs


class Command(BaseCommand):
    def print(self, *x, **y):
        self.stdout.write(" ".join(str(xx) for xx in x), ending="\n", **y)

    def add_arguments(self, parser):
        ofn = f'pgp_documents-{timezone.now().strftime("%Y%m%dT%H%M%S")}.csv'
        parser.add_argument(
            "-o", "--output_filename", type=str, default=ofn, required=False
        )

    def handle(self, *args, **options):
        began = time.time()
        self.print("Starting CSV export")

        export_docs(fn=options["output_filename"])

        self.print(f"Finished CSV export in {time.time()-began:01f} seconds")
