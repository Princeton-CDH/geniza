import time

from django.core.management.base import BaseCommand

from geniza.corpus.csv_export import export_docs


class Command(BaseCommand):
    # def add_arguments(self, parser):
    #     parser.add_argument("pgpid", nargs="*")

    def print(self, *x, **y):
        self.stdout.write(" ".join(str(xx) for xx in x), ending="\n", **y)

    def handle(self, *args, **options):
        began = time.time()
        self.print("Starting CSV export")
        export_docs()
        self.print(f"Finished CSV export in {time.time()-began:02f} seconds")
