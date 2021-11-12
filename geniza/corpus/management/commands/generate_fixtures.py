import sys
from os import remove

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("pgpid", nargs="*")

    def handle(self, *args, **options):
        """Export fixtures from the database, given a list of PGPIDs.

        Example usage with PGPIDs 1, 20, and 1234: python manage.py generate_fixtures 1 20 1234"""

        if not options["pgpid"]:
            raise Exception("PGPID list argument is required")

        pgpids = [int(i) for i in options["pgpid"]]

        fixtures = [
            "geniza/corpus/fixtures/documents.json",
            "geniza/corpus/fixtures/authorships.json",
            "geniza/corpus/fixtures/document_dependents.json",
        ]

        # Dump documents
        with open(fixtures[0], "w") as f0:
            call_command(
                "dump_object",
                "corpus.document",
                kitchensink=True,
                natural=True,
                query='{"pk__in": %s}' % pgpids,
                stdout=f0,
            )

        # Dump authorships
        with open(fixtures[1], "w") as f1:
            call_command(
                "dump_object",
                "footnotes.authorship",
                kitchensink=True,
                natural=True,
                query='{"source__footnote__object_id__in": %s}' % pgpids,
                stdout=f1,
            )

        # This stdout rerouting is needed with custom_dump and merge_fixtures, but
        # the others work with call_command's stdout kwarg

        # Dump document related objects
        sysout = sys.stdout
        with open(fixtures[2], "w") as f2:
            sys.stdout = f2
            call_command("custom_dump", "document", *pgpids, natural=True)

        # Merge all dumped fixtures
        with open("geniza/corpus/fixtures/test_documents.json", "w") as merged:
            sys.stdout = merged
            call_command("merge_fixtures", *fixtures)

        sys.stdout = sysout

        # Clean up unmerged fixtures
        for unmerged in fixtures:
            remove(unmerged)
