"""
Script to remove machine-generated Arabic-script transliterations ingested by
the add_translation command from a list of documents. Deletes the digital
translation footnote for the transliteration source on each document, along
with its annotations, logs the deletions, and reindexes the documents.
The source itself is kept, so it can be reused by later ingests.

Intended to be run manually from the shell as follows:
./manage.py remove_translation PGPID [PGPID ...]

Use --dry-run to report what would be removed without deleting anything.
"""

from django.conf import settings
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from parasolr.django.signals import IndexableSignalHandler

from geniza.corpus.management.commands import add_translation
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source


class Command(BaseCommand):
    """Remove machine-generated transliterations from documents"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "pgpids", nargs="+", type=int, help="PGPIDs of the documents"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be removed without deleting anything",
        )

    def handle(self, *args, **options):
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        source = Source.objects.filter(
            title_en=add_translation.Command.article["title_en"],
            source_type__type="Article",
        ).first()
        if not source:
            raise CommandError("No transliteration source found; nothing to remove")

        # disconnect solr indexing signals; this script will index documents manually
        IndexableSignalHandler.disconnect()

        removed, not_found = [], []
        for pgpid in options["pgpids"]:
            footnotes = Footnote.objects.filter(
                doc_relation__contains=Footnote.DIGITAL_TRANSLATION,
                source=source,
                content_type=ContentType.objects.get_for_model(Document),
                object_id=pgpid,
            )
            if not footnotes.exists():
                not_found.append(str(pgpid))
                continue
            with transaction.atomic():
                for footnote in footnotes:
                    # pk is unset on delete, so keep it for reporting
                    footnote_pk = footnote.pk
                    n_annotations = footnote.annotation_set.count()
                    if not options["dry_run"]:
                        self.log_deletion(footnote)
                        # annotations are deleted with the footnote
                        footnote.delete()
                    self.stdout.write(
                        "PGPID %d: %s footnote %d with %d annotation(s)"
                        % (
                            pgpid,
                            "would remove" if options["dry_run"] else "removed",
                            footnote_pk,
                            n_annotations,
                        )
                    )
            removed.append(str(pgpid))
            if not options["dry_run"]:
                self.index(pgpid)

        self.stdout.write(
            self.style.SUCCESS(
                "%s transliterations from %d document(s)"
                % ("Would remove" if options["dry_run"] else "Removed", len(removed))
            )
        )
        if removed:
            self.stdout.write(
                "%s PGPIDs: %s"
                % (
                    "Would remove" if options["dry_run"] else "Removed",
                    ", ".join(removed),
                )
            )
        if not_found:
            self.stdout.write(
                "No transliteration found for PGPIDs: %s" % ", ".join(not_found)
            )

    def index(self, pgpid):
        """Reindex a document in solr, warning if indexing fails"""
        try:
            Document.objects.get(pk=pgpid).index()
        except Exception as err:
            self.stdout.write(
                self.style.WARNING(
                    "Could not index document %d; reindex manually (%s)" % (pgpid, err)
                )
            )

    def log_deletion(self, obj):
        """Create a DELETION log entry for an object removed by this script"""
        LogEntry.objects.log_action(
            user_id=self.script_user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message="Removed machine-generated digital translation",
            action_flag=DELETION,
        )
