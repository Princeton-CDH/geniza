from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.admin.models import DELETION, LogEntry
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.annotations.models import Annotation
from geniza.corpus.management.commands.add_translation import Command as AddCommand
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source

CANVAS = "https://example.com/iiif/canvas/1"


def add_translation(doc, tmp_path):
    """ingest a transliteration for a document with the add_translation command"""
    csv_path = tmp_path / ("%d.csv" % doc.pk)
    csv_path.write_text(
        "Transliterated,JA,PGPID\nيا,יא,%d\n" % doc.pk, encoding="utf-8"
    )
    with patch.object(Document, "iiif_images", return_value={CANVAS: {}}):
        call_command(
            "add_translation",
            str(csv_path),
            "-m",
            "Test MT model",
            "--model-version",
            "1.0",
            stdout=StringIO(),
        )
    return doc.digital_translations().get()


def remove_translation(*args):
    out = StringIO()
    call_command("remove_translation", *[str(a) for a in args], stdout=out)
    return out.getvalue()


@pytest.mark.django_db
@patch.object(Document, "index")
class TestRemoveTranslation:
    def test_no_source(self, mock_index, document):
        with pytest.raises(CommandError, match="No transliteration source"):
            remove_translation(document.pk)

    def test_remove(self, mock_index, document, footnote, tmp_path):
        translation = add_translation(document, tmp_path)
        other_doc = Document.objects.create()
        mock_index.reset_mock()

        output = remove_translation(document.pk, other_doc.pk)

        assert not Footnote.objects.filter(pk=translation.pk).exists()
        assert not Annotation.objects.filter(footnote_id=translation.pk).exists()
        # other footnotes on the document are untouched
        assert Footnote.objects.filter(pk=footnote.pk).exists()
        # source is kept for later ingests
        assert Source.objects.filter(title_en=AddCommand.article["title_en"]).exists()
        assert LogEntry.objects.filter(
            object_id=str(translation.pk), action_flag=DELETION
        ).exists()
        mock_index.assert_called_once()
        assert (
            "PGPID %d: removed footnote %d with 1 annotation(s)"
            % (document.pk, translation.pk)
            in output
        )
        assert "Removed transliterations from 1 document(s)" in output
        assert "Removed PGPIDs: %d\n" % document.pk in output
        assert "No transliteration found for PGPIDs: %d" % other_doc.pk in output

    def test_dry_run(self, mock_index, document, tmp_path):
        translation = add_translation(document, tmp_path)
        mock_index.reset_mock()

        output = remove_translation(document.pk, "--dry-run")

        assert Footnote.objects.filter(pk=translation.pk).exists()
        assert translation.annotation_set.exists()
        assert not LogEntry.objects.filter(action_flag=DELETION).exists()
        mock_index.assert_not_called()
        assert "would remove footnote %d" % translation.pk in output
        assert "Would remove PGPIDs: %d" % document.pk in output
