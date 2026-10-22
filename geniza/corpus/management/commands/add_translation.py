"""
Script to add machine-generated Arabic-script transliterations of Judaeo-Arabic
documents as digital translations, from a CSV with columns PGPID, JA (the
Judaeo-Arabic text the transliteration was generated from) and Transliterated
(the Arabic-script transliteration, aligned word for word with JA).

Gets or creates a single source for the model (shared across all documents
ingested with the same model name and version) and a digital translation
footnote for that source on each document. When the document has a digital
edition, the transliteration is split to mirror it: one annotation per
transcription block, on the same canvas, with the same label, position and
lines, so that line numbering matches across transcription and translation.
Otherwise, the transliteration is added as a single block on the document's
first image (or a placeholder canvas if the document has no images).

Intended to be run manually from the shell as follows:
./manage.py add_translation transliterations.csv -m "Model name" --model-version 1.0
"""

import csv
import html
import re
import unicodedata
from copy import deepcopy
from difflib import SequenceMatcher

from bs4 import BeautifulSoup, NavigableString
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from parasolr.django.signals import IndexableSignalHandler

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source, SourceLanguage, SourceType

#: editorial marks in transcriptions that are not part of the words
EDITORIAL_MARKS_RE = re.compile(r"[\[\]/.?!()]")


def tokenize(text):
    """Split Judaeo-Arabic text into words, removing editorial marks;
    a | marks a break within a word, so it is treated as a word boundary."""
    return EDITORIAL_MARKS_RE.sub("", text.replace("|", " ")).split()


class Command(BaseCommand):
    """Add machine-generated transliterations from a CSV as digital translations"""

    help = __doc__

    #: language code of the transliterations
    language_code = "ar"

    #: minimum share of CSV words that must match the transcription words
    #: for a document's transliteration to be split along transcription lines
    min_match = 0.8

    def add_arguments(self, parser):
        parser.add_argument(
            "csv", help="Path to a CSV with PGPID, JA, and Transliterated columns"
        )
        parser.add_argument(
            "-m",
            "--model-name",
            required=True,
            help="Name of the model that generated the transliterations",
        )
        parser.add_argument(
            "--model-version",
            required=True,
            help="Version number of the model that generated the transliterations",
        )
        parser.add_argument(
            "-p",
            "--pgpid",
            type=int,
            action="append",
            help="Only ingest rows for this PGPID; repeat for multiple documents",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how each row would be ingested without saving anything",
        )

    def handle(self, *args, **options):
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.language = SourceLanguage.objects.get(code=self.language_code)

        with open(options["csv"], encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            missing = {"PGPID", "JA", "Transliterated"} - set(reader.fieldnames or [])
            if missing:
                raise CommandError("CSV is missing columns: %s" % ", ".join(missing))
            rows = [
                row
                for row in reader
                if not options["pgpid"] or int(row["PGPID"]) in options["pgpid"]
            ]

        # disconnect solr indexing signals; this script will index documents manually
        IndexableSignalHandler.disconnect()

        self.source = None
        added, skipped = 0, []
        for row in rows:
            try:
                with transaction.atomic():
                    doc = self.ingest_row(row, options)
                    if options["dry_run"]:
                        transaction.set_rollback(True)
                added += 1
                if not options["dry_run"]:
                    self.index(doc)
            except CommandError as err:
                skipped.append(row["PGPID"])
                self.stdout.write(self.style.WARNING("Skipped: %s" % err))

        self.stdout.write(
            self.style.SUCCESS(
                "%s %d translation(s); skipped %d"
                % ("Would add" if options["dry_run"] else "Added", added, len(skipped))
            )
        )
        if skipped:
            self.stdout.write("Skipped PGPIDs: %s" % ", ".join(skipped))

    def ingest_row(self, row, options):
        """Create the translation footnote and annotations for one CSV row;
        returns the document"""
        pgpid = int(row["PGPID"])
        try:
            doc = Document.objects.get(pk=pgpid)
        except Document.DoesNotExist:
            raise CommandError("Document not found for PGPID %d" % pgpid)
        ja_words = tokenize(unicodedata.normalize("NFC", row["JA"]))
        ar_words = unicodedata.normalize("NFC", row["Transliterated"]).split()
        if not ar_words:
            raise CommandError("PGPID %d has no transliteration" % pgpid)
        if len(ja_words) != len(ar_words):
            raise CommandError(
                "PGPID %d: JA and transliteration word counts differ (%d, %d)"
                % (pgpid, len(ja_words), len(ar_words))
            )

        # get source on every row, since a dry run rolls it back
        self.source = self.get_source(
            "%s %s" % (options["model_name"], options["model_version"])
        )
        footnote = self.get_footnote(doc, self.source)
        # don't add a second copy of the translation on rerun
        if footnote.annotation_set.exists():
            raise CommandError(
                "PGPID %d already has a translation from %s (footnote %d)"
                % (pgpid, self.source.title, footnote.pk)
            )

        aligned = self.align_to_edition(doc, ja_words, ar_words)
        if aligned:
            blocks, match = aligned
            for content in blocks:
                self.create_annotation(footnote, content)
                if options["dry_run"]:
                    self.stdout.write(
                        "  [%s] %s"
                        % (content["body"][0]["label"], content["body"][0]["value"])
                    )
            message = "%d block(s) aligned to transcription (%d%% word match)" % (
                len(blocks),
                match * 100,
            )
        else:
            canvas_uri, placeholder = self.get_canvas_uri(doc)
            self.create_annotation(
                footnote,
                self.annotation_content(
                    "<p>%s</p>" % html.escape(" ".join(ar_words)),
                    {
                        "source": {"id": canvas_uri, "type": "Canvas"},
                        # nearly full canvas, to make it easier to edit zones
                        "selector": {
                            "type": "FragmentSelector",
                            "conformsTo": "http://www.w3.org/TR/media-frags/",
                            "value": "xywh=percent:1,1,98,98",
                        },
                    },
                ),
            )
            message = "single block on %scanvas %s" % (
                "placeholder " if placeholder else "",
                canvas_uri,
            )

        self.stdout.write("PGPID %d: footnote %d, %s" % (pgpid, footnote.pk, message))
        return doc

    def align_to_edition(self, doc, ja_words, ar_words):
        """Split the transliteration along the lines of the document's best-matching
        digital edition. Returns a list of annotation contents, one per transcription
        block, and the share of words matched; or None if there is no digital edition
        that matches well enough."""
        best = None
        for edition in doc.digital_editions():
            blocks = [
                (block, *self.block_lines(block))
                for block in edition.annotation_set.filter(block__isnull=True).order_by(
                    "content__schema:position", "created"
                )
            ]
            # each transcription word, with the (block, line) index it belongs to
            words = [
                (word, (b, l))
                for b, (_, _, lines) in enumerate(blocks)
                for l, line in enumerate(lines)
                for word in tokenize(line.get_text(" ") if line else "")
            ]
            if not words:
                continue
            word_lines = self.assign_lines(
                [w for w, _ in words], [loc for _, loc in words], ja_words
            )
            match = word_lines["matched"] / len(ja_words)
            if not best or match > best[2]:
                best = (blocks, word_lines["lines"], match)

        if not best or best[2] < self.min_match:
            return None
        blocks, lines, match = best

        # gather transliterated words per transcription line
        ar_lines = {}
        for ar_word, loc in zip(ar_words, lines):
            ar_lines.setdefault(loc, []).append(ar_word)

        contents = []
        for b, (block, soup, line_elements) in enumerate(blocks):
            contents.append(
                self.annotation_content(
                    self.block_html(soup, line_elements, b, ar_lines),
                    deepcopy(block.content.get("target", {})),
                    label=block.label or "",
                    position=block.content.get("schema:position"),
                )
            )
        return contents, match

    def assign_lines(self, edition_words, edition_lines, ja_words):
        """Align CSV words to transcription words and return the transcription
        (block, line) for each CSV word, plus the number of words matched exactly.
        Words with no counterpart are assigned to the line of the preceding word."""
        matcher = SequenceMatcher(None, edition_words, ja_words, autojunk=False)
        lines = []
        matched = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                matched += j2 - j1
            for j in range(j1, j2):
                if i2 > i1:
                    # spread replaced words proportionally over the replaced range
                    lines.append(edition_lines[i1 + (j - j1) * (i2 - i1) // (j2 - j1)])
                else:
                    # inserted words: line of the preceding (or first) word
                    lines.append(lines[-1] if lines else edition_lines[0])
        return {"lines": lines, "matched": matched}

    def block_lines(self, block):
        """Parse a transcription block's html; returns the parsed html and its line
        elements: each list item, plus any other top-level element with text. For a
        block with line annotations, returns no parsed html and one line per annotation.
        """
        if block.has_lines:
            return None, [
                BeautifulSoup(line.body_content or "", "html.parser")
                for line in block.lines.all().order_by("content__schema:position")
            ]
        soup = BeautifulSoup(block.body_content or "", "html.parser")
        lines = []
        for element in soup.contents:
            if getattr(element, "name", None) in ["ol", "ul"]:
                lines += element.find_all("li")
            elif getattr(element, "name", None) and element.get_text().strip():
                lines.append(element)
        return soup, lines

    def block_html(self, soup, line_elements, b, ar_lines):
        """Html for the translation of a transcription block, with the same
        structure as the transcription and each line's text replaced by its
        transliteration. Lines with no words (e.g. ellipses) are kept as is."""
        texts = [
            " ".join(ar_lines.get((b, l), [])) for l, line in enumerate(line_elements)
        ]
        if soup is None:
            return "<ol>%s</ol>" % "".join(
                "<li>%s</li>" % html.escape(text) for text in texts
            )
        for line, text in zip(line_elements, texts):
            if text or tokenize(line.get_text(" ")):
                line.clear()
                line.append(NavigableString(text))
        return str(soup)

    def get_canvas_uri(self, doc):
        """Return the URI of the document's first image canvas, or a placeholder canvas
        on its first textblock if it has no images, and whether it is a placeholder."""
        canvas_uri = next(iter(doc.iiif_images(filter_side=True)), None)
        if canvas_uri:
            return canvas_uri, False
        textblock = doc.textblock_set.order_by("order").first()
        if not textblock:
            raise CommandError(
                "Document %d has no images or fragments to place a translation on"
                % doc.pk
            )
        # same format as placeholder canvases in the annotation editor
        return f"{doc.permalink}iiif/textblock/{textblock.pk}/canvas/1/", True

    def get_source(self, title):
        """Get or create the machine learning model source with the given title"""
        (model, _) = SourceType.objects.get_or_create(type="Machine learning model")
        (source, created) = Source.objects.get_or_create(
            title_en=title,
            source_type=model,
        )
        if created:
            source.languages.add(self.language)
            self.log_addition(
                source, "Created new source for machine-generated digital translation"
            )
        return source

    def get_footnote(self, document, source):
        """Get or create a digital translation footnote for this source and document"""
        try:
            return Footnote.objects.get(
                doc_relation__contains=Footnote.DIGITAL_TRANSLATION,
                source__pk=source.pk,
                content_type=ContentType.objects.get_for_model(Document),
                object_id=document.pk,
            )
        except Footnote.DoesNotExist:
            footnote = Footnote.objects.create(
                content_object=document,
                source=source,
                doc_relation=[Footnote.DIGITAL_TRANSLATION],
            )
            self.log_addition(
                footnote,
                "Created new footnote for machine-generated digital translation",
            )
            return footnote

    def annotation_content(self, body_html, target, label="", position=1):
        """Block-level translation annotation content"""
        return {
            "body": [
                {
                    "type": "TextualBody",
                    "format": "text/html",
                    "label": label,
                    "value": body_html,
                }
            ],
            "target": target,
            "motivation": ["sc:supplementing", "translating"],
            "schema:position": position or 1,
        }

    def create_annotation(self, footnote, content):
        """Create and log a translation annotation with the given content"""
        anno = Annotation(footnote=footnote)
        anno.set_content(content)
        anno.save()
        self.log_addition(anno, "Imported machine-generated digital translation")
        return anno

    def index(self, doc):
        """Reindex a document in solr, warning if indexing fails"""
        try:
            doc.index()
        except Exception as err:
            self.stdout.write(
                self.style.WARNING(
                    "Could not index document %d; reindex manually (%s)" % (doc.pk, err)
                )
            )

    def log_addition(self, obj, message):
        """Create an ADDITION log entry for an object created by this script"""
        LogEntry.objects.log_action(
            user_id=self.script_user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message=message,
            action_flag=ADDITION,
        )
