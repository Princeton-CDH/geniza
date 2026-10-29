import csv
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.annotations.models import Annotation
from geniza.corpus.management.commands.add_translation import Command, tokenize
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source

CANVAS = "https://example.com/iiif/canvas/1"
TARGET = {
    "source": {"id": CANVAS, "type": "Canvas"},
    "selector": {"type": "FragmentSelector", "value": "xywh=percent:10,10,50,50"},
}


@pytest.fixture
def edition(document, source):
    """digital edition with a main block, a trailing paragraph, and a margin block"""
    footnote = Footnote.objects.create(
        content_object=document, source=source, doc_relation=[Footnote.DIGITAL_EDITION]
    )
    Annotation.objects.create(
        footnote=footnote,
        content={
            "body": [
                {
                    "value": "<ol><li>]או יא[</li><li>הק[הל] [ ]</li><li>[ ]</li>"
                    + "<li>לחלא|ל //קצד//</li></ol><p>...</p>"
                }
            ],
            "target": TARGET,
            "schema:position": 1,
        },
    )
    Annotation.objects.create(
        footnote=footnote,
        content={
            "body": [{"label": "margin", "value": "<ol><li>תמנע ען י.ע</li></ol>"}],
            "target": TARGET,
            "schema:position": 2,
        },
    )
    return footnote


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Transliterated", "JA", "PGPID"])
        writer.writeheader()
        for pgpid, ja, transliterated in rows:
            writer.writerow(
                {"PGPID": pgpid, "JA": ja, "Transliterated": transliterated}
            )
    return str(path)


@pytest.fixture
def translation_csv(tmp_path, document):
    return write_csv(
        tmp_path / "translations.csv",
        [
            (
                document.pk,
                "או יא הקהל לחלא ל קצד תמנע ען יע",
                "او يا القهل لحلا ل قصد تمنع عن يع",
            )
        ],
    )


def add_translation(csv_path, *args, images={CANVAS: {}}):
    """call the command with a fixed model name and version and mocked images"""
    out = StringIO()
    with patch.object(Document, "iiif_images", return_value=images):
        call_command(
            "add_translation",
            csv_path,
            "-m",
            "Test MT model",
            "--model-version",
            "1.0",
            *args,
            stdout=out,
        )
    return out.getvalue()


def test_tokenize():
    assert tokenize("]או יא[ הק[הל] [ ] לחלא|ל //קצד// י.ע [מוה?]") == [
        "או",
        "יא",
        "הקהל",
        "לחלא",
        "ל",
        "קצד",
        "יע",
        "מוה",
    ]


def test_assign_lines():
    cmd = Command()
    result = cmd.assign_lines(
        ["a", "b", "c", "d"], [0, 0, 1, 1], ["x", "a", "b", "b2", "c", "e"]
    )
    # leading insert goes to first line; inserted word to preceding word's line;
    # replaced word to the replaced word's line
    assert result == {"lines": [0, 0, 0, 0, 1, 1], "matched": 3}


@pytest.mark.django_db
class TestAddTranslation:
    @patch.object(Document, "index")
    def test_handle_aligned(self, mock_index, document, edition, translation_csv):
        output = add_translation(translation_csv)

        footnote = document.digital_translations().get()
        source = footnote.source
        # source is the article describing the model, with the model noted
        assert source.source_type.type == "Article"
        assert source.title == Command.article["title_en"]
        assert source.journal == Command.article["journal"]
        assert source.volume == "NLP4DH"
        assert source.year == 2025
        assert source.url == "https://doi.org/10.46298/jdmdh.15020"
        assert (
            source.notes
            == "Machine-generated transliterations by model Test MT model 1.0"
        )
        assert list(source.languages.values_list("code", flat=True)) == ["ar"]
        assert [str(a.creator) for a in source.authorship_set.all()] == [
            "Abdellatif, Mohamed",
            "Bretheim, Joel",
            "Rustow, Marina",
        ]
        # cited like any other article (with LTR marks, since the language is RTL)
        assert source.display() == (
            "Mohamed Abdellatif, Joel Bretheim and Marina Rustow, "
            + '"Machine Transliteration of Long Text with Error '
            + 'Detection and Correction‎" (in Arabic), Journal of Data Mining & '
            + "Digital Humanities‎ NLP4DH (2025)."
        )

        main, margin = footnote.annotation_set.order_by("content__schema:position")
        # same canvas, zone, label, and position as the transcription blocks
        for anno, position, label in [(main, 1, ""), (margin, 2, "margin")]:
            assert anno.block is None
            assert anno.content["target"] == TARGET
            assert anno.content["schema:position"] == position
            assert anno.label == label
            assert anno.content["motivation"] == ["sc:supplementing", "translating"]
        # same lines as the transcription; line with no words left empty,
        # paragraph with no words kept as is
        assert main.body_content == (
            "<ol><li>او يا</li><li>القهل</li><li>[ ]</li>"
            + "<li>لحلا ل قصد</li></ol><p>...</p>"
        )
        assert margin.body_content == "<ol><li>تمنع عن يع</li></ol>"

        for obj in [source, footnote, main, margin]:
            assert LogEntry.objects.filter(
                object_id=str(obj.pk), action_flag=ADDITION
            ).exists()
        mock_index.assert_called_once()
        assert "2 block(s) aligned to transcription (100% word match)" in output
        assert "Added 1 translation(s); skipped 0" in output

        # rerun on the same document should not add a second translation
        output = add_translation(translation_csv)
        assert "already has a translation" in output
        assert footnote.annotation_set.count() == 2

    @patch.object(Document, "index")
    def test_handle_line_annotations(self, mock_index, document, source, tmp_path):
        footnote = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        block = Annotation.objects.create(
            footnote=footnote, content={"target": TARGET, "schema:position": 1}
        )
        for i, text in enumerate(["או יא", "הקהל"], start=1):
            Annotation.objects.create(
                footnote=footnote,
                block=block,
                content={
                    "body": [{"value": text}],
                    "textGranularity": "line",
                    "schema:position": i,
                },
            )
        csv_path = write_csv(
            tmp_path / "t.csv", [(document.pk, "או יא הקהל", "او يا القهل")]
        )
        add_translation(csv_path)
        anno = document.digital_translations().get().annotation_set.get()
        assert anno.body_content == "<ol><li>او يا</li><li>القهل</li></ol>"

    @patch.object(Document, "index")
    def test_handle_no_edition(self, mock_index, document, translation_csv):
        output = add_translation(translation_csv)
        anno = document.digital_translations().get().annotation_set.get()
        assert anno.target_source_id == CANVAS
        assert anno.body_content == "<p>او يا القهل لحلا ل قصد تمنع عن يع</p>"
        assert "single block on canvas %s" % CANVAS in output

        # placeholder when there are no images
        other_doc = Document.objects.create()
        other_doc.textblock_set.create(fragment=document.fragments.first())
        csv_path = write_csv(
            translation_csv.replace(".csv", "2.csv"), [(other_doc.pk, "יא", "يا")]
        )
        output = add_translation(csv_path, images={})
        anno = other_doc.digital_translations().get().annotation_set.get()
        assert "/iiif/textblock/" in anno.target_source_id
        assert "single block on placeholder canvas" in output
        # same source for both documents
        assert Source.objects.filter(title_en=Command.article["title_en"]).count() == 1

    @patch.object(Document, "index")
    def test_handle_poor_match(self, mock_index, document, edition, tmp_path):
        # words that don't match the transcription: fall back to a single block
        csv_path = write_csv(
            tmp_path / "t.csv", [(document.pk, "x y z", "او يا القهل")]
        )
        output = add_translation(csv_path)
        assert "single block on canvas" in output

    def test_handle_skipped(self, document, translation_csv, tmp_path):
        csv_path = write_csv(
            tmp_path / "t.csv",
            [(0, "יא", "يا"), (document.pk, "או יא", "او"), (document.pk, "יא", "")],
        )
        output = add_translation(csv_path)
        assert "Document not found for PGPID 0" in output
        assert "word counts differ (2, 1)" in output
        assert "has no transliteration" in output
        assert "Added 0 translation(s); skipped 3" in output
        # nothing should have been created
        assert not document.digital_translations().exists()
        assert not Source.objects.filter(title_en=Command.article["title_en"]).exists()

    @patch.object(Document, "index")
    def test_handle_limit(self, mock_index, document, tmp_path):
        csv_path = write_csv(
            tmp_path / "t.csv",
            [(document.pk, "יא", "يا"), (0, "יא", "يا"), (0, "יא", "يا")],
        )
        # only the first two rows are read
        output = add_translation(csv_path, "-n", "2")
        assert "Added 1 translation(s); skipped 1" in output
        assert "Added PGPIDs: %d\n" % document.pk in output
        assert "Skipped PGPIDs: 0\n" in output
        with pytest.raises(CommandError, match="positive"):
            add_translation(csv_path, "-n", "0")

    @patch.object(Document, "index")
    def test_handle_dry_run(self, mock_index, document, edition, translation_csv):
        output = add_translation(translation_csv, "--dry-run")
        assert "[margin] <ol><li>تمنع عن يع</li></ol>" in output
        assert "Would add 1 translation(s)" in output
        assert "Would add PGPIDs: %d" % document.pk in output
        assert not document.digital_translations().exists()
        assert not Source.objects.filter(title_en=Command.article["title_en"]).exists()
        mock_index.assert_not_called()

    @patch.object(Document, "index", side_effect=ConnectionError("no solr"))
    def test_handle_index_error(self, mock_index, document, translation_csv):
        output = add_translation(translation_csv)
        assert "Could not index document" in output
        assert document.digital_translations().get().annotation_set.exists()
