import os.path
from io import StringIO
from unittest.mock import ANY, MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.core.management import call_command
from djiffy.models import Canvas
from eulxml import xmlmap
from parasolr.django.signals import IndexableSignalHandler

from geniza.corpus.management.commands.escr_alto_to_annotation import (
    Command,
    EscriptoriumAlto,
)
from geniza.corpus.models import Document, TextBlock

fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures")

xmlfile = os.path.join(fixture_dir, "PGPID_6032_MS-TS-AS-00152-00383_0.xml")


class TestEscrToAltoAnnotation:
    cmd = Command()

    def test_fields(self):
        alto = xmlmap.load_xmlobject_from_file(xmlfile, EscriptoriumAlto)
        assert "PGPID_6032" in alto.filename
        assert len(alto.tags) == 18
        assert alto.printspace
        assert len(alto.printspace.textblocks) == 1
        tb = alto.printspace.textblocks[0]
        assert "eSc_textblock_" in tb.id
        assert tb.block_type_id == "BT2"
        # find first tag in tag list whose id matches block type id
        tag_matches = filter(lambda t: t.id == tb.block_type_id, alto.tags)
        tag = next(tag_matches, None)
        assert tag and tag.label == "Main"
        assert tb.polygon
        assert len(tb.lines) == 14
        line = tb.lines[0]
        assert line.polygon
        assert line.content == "חטל אללה בקאך נ["

    def test_scale_polygon(self):
        alto = xmlmap.load_xmlobject_from_file(xmlfile, EscriptoriumAlto)
        block = alto.printspace.textblocks[0]
        # some of the polygon points that will be scaled
        assert "1663 319 1668 391 1648 424" in str(block.polygon)

        # should divide each number by the scale factor
        scaled_polygon = self.cmd.scale_polygon(block.polygon, 0.5)
        assert f"{1663/0.5} {319/0.5} {1668/0.5} {391/0.5} {1648/0.5} {424/0.5}" in str(
            scaled_polygon
        )

        # if scale factor produces irrational numbers, should round to 4 decimal places
        scaled_polygon = self.cmd.scale_polygon(block.polygon, 3)
        assert str(1663 / 3) not in str(scaled_polygon)
        assert str(round(1663 / 3, 4)) in str(scaled_polygon)

    def test_create_block_annotation(self):
        alto = xmlmap.load_xmlobject_from_file(xmlfile, EscriptoriumAlto)
        block = alto.printspace.textblocks[0]
        with patch.object(self.cmd, "scale_polygon") as scale_mock:
            scale_mock.return_value = "100 200"
            anno_content = self.cmd.create_block_annotation(block, "mock_canvas", 2)

            # anno body should contain the transcription text
            assert "<li>חטל אללה בקאך נ[</li>" in anno_content["body"][0]["value"]

            # anno target source should be canvas
            assert anno_content["target"]["source"]["id"] == "mock_canvas"

            # selector should be svg containing mock result polygon points
            assert (
                '<svg><polygon points="100 200">'
                in anno_content["target"]["selector"]["value"]
            )

        # block without polygon should cover most of entire image with fragmentselector
        del block.polygon
        anno_content = self.cmd.create_block_annotation(block, "mock_canvas", 2)
        assert anno_content["target"]["selector"]["value"] == "xywh=percent:1,1,98,98"

    def test_get_manifest(self, document):
        manifests = [b.fragment.manifest for b in document.textblock_set.all()]
        id = manifests[0].short_id
        out = StringIO()
        self.cmd.stdout = out
        self.cmd.canvas_errors = set()
        # short id matches, should get manifest
        assert self.cmd.get_manifest(document, id, "").pk == manifests[0].pk

        # short id doesn't match, should get first manifest on document
        assert self.cmd.get_manifest(document, None, "").pk == manifests[0].pk
        assert "Could not find manifest" in out.getvalue()
        assert f"(of {len(manifests)})" in out.getvalue()

        # no manifests on document, no short id match, should return None
        doc_2 = Document.objects.create()
        assert self.cmd.get_manifest(doc_2, None, "") is None
        assert "Could not find manifests" in out.getvalue()

    def test_get_canvas(self, document):
        manifests = [b.fragment.manifest for b in document.textblock_set.all()]
        id = "test"
        canvas = Canvas.objects.create(
            short_id=id,
            manifest=manifests[0],
            label="fake image",
            iiif_image_id="http://example.co/iiif/ts-1/00001",
            order=1,
        )
        self.cmd.canvas_errors = set()
        # short id matches, should get canvas
        assert self.cmd.get_canvas(manifests[0], id, "").pk == canvas.pk

        # short id doesn't match, should get first canvas on manifest
        assert self.cmd.get_canvas(manifests[0], None, "").pk == canvas.pk

        # no manifest, should return None
        assert self.cmd.get_canvas(None, id, "") is None

    def test_get_footnote(self, document):
        self.cmd.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # footnote does not exist, should create and log
        fn = self.cmd.get_footnote(document)
        assert fn.object_id == document.pk
        assert LogEntry.objects.filter(object_id=fn.pk, action_flag=ADDITION).exists()

        # footnote already exists, should find it
        assert self.cmd.get_footnote(document).pk == fn.pk

    @pytest.mark.django_db
    def test_handle(self, fragment):
        with patch.object(Command, "ingest_xml") as mock_ingest:
            out = StringIO()
            call_command("escr_alto_to_annotation", xmlfile, stdout=out)
            # should print a message and call the ingest function once per xml file
            assert "Processing %s" % xmlfile in out.getvalue()
            mock_ingest.assert_called_once_with(xmlfile)
            assert "Done! Processed 1 file(s)." in out.getvalue()

        # no document match, should report files that failed this way
        out = StringIO()
        call_command("escr_alto_to_annotation", xmlfile, stdout=out)
        assert "1 file(s) failed to match a PGP document" in out.getvalue()
        assert f"\t- {xmlfile}" in out.getvalue()

        # no canvas match, should report files that failed this way
        doc = Document.objects.create(old_pgpids=[6032])
        TextBlock.objects.create(document=doc, fragment=fragment)
        out = StringIO()
        call_command("escr_alto_to_annotation", xmlfile, stdout=out)
        print(out.getvalue())
        assert "1 file(s) failed to match a specific image" in out.getvalue()
        assert f"\t- {xmlfile}" in out.getvalue()

    @pytest.mark.django_db
    def test_ingest_xml(self, document, annotation_json):
        alto = xmlmap.load_xmlobject_from_file(xmlfile, EscriptoriumAlto)

        # no matching document, should print error and return
        out = StringIO()
        call_command("escr_alto_to_annotation", xmlfile, stdout=out)
        assert "Could not match document; skipping" in out.getvalue()

        # add as fixture's old PGPID, should not skip
        document.old_pgpids = [6032]
        document.save()
        out = StringIO()
        call_command("escr_alto_to_annotation", xmlfile, stdout=out)
        assert "Could not match document; skipping" not in out.getvalue()

        # no canvas, should create annotations on placeholder
        with patch.object(Command, "create_block_annotation") as mock_create_anno:
            mock_create_anno.return_value = annotation_json
            call_command("escr_alto_to_annotation", xmlfile, stdout=out)
            mock_create_anno.assert_called()
            # placeholder canvas URI
            assert (
                f"{document.permalink}iiif/textblock/"
                in mock_create_anno.call_args.args[1]
            )
            # placeholder width == 640
            assert mock_create_anno.call_args.args[2] * 640 == int(
                alto.printspace.node.attrib["WIDTH"]
            )

        # canvas exists, should get uri
        manifests = [b.fragment.manifest for b in document.textblock_set.all()]
        canvas = Canvas.objects.create(
            short_id="test",
            manifest=manifests[0],
            label="fake image",
            iiif_image_id="http://example.co/iiif/ts-1/00001",
            uri="http://example.co/iiif/ts-1/canvas/1",
            order=1,
        )
        # disconnect indexing signal handler
        IndexableSignalHandler.disconnect()
        with patch.object(Command, "create_block_annotation") as mock_create_anno:
            mock_create_anno.return_value = annotation_json
            # mock iiif image to avoid network req
            with patch.object(Canvas, "image"):
                call_command("escr_alto_to_annotation", xmlfile, stdout=out)
                mock_create_anno.assert_called_with(ANY, canvas.uri, ANY)

        # should have created log entries for the new annotations
        assert LogEntry.objects.filter(
            change_message="Imported from eScriptorium HTR ALTO",
            action_flag=ADDITION,
        ).exists()
