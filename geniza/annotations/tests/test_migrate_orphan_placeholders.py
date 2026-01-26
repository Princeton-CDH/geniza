import csv
from unittest.mock import patch

import pytest
from django.core.management import call_command
from parasolr.django.signals import IndexableSignalHandler

from geniza.annotations.management.commands.migrate_orphan_placeholders import Command
from geniza.annotations.models import Annotation
from geniza.corpus.models import Document, Fragment, TextBlock
from geniza.corpus.tests.conftest import MockImporter
from geniza.footnotes.models import Footnote


@pytest.mark.django_db
def test_group_by_document(annotation, source):
    # create some documents
    doc1 = Document.objects.create()
    footnote1 = Footnote.objects.create(
        source=source, content_object=doc1, doc_relation=Footnote.DIGITAL_EDITION
    )
    doc2 = Document.objects.create()
    footnote2 = Footnote.objects.create(
        source=source, content_object=doc2, doc_relation=Footnote.DIGITAL_EDITION
    )

    # annotations attached by target_source_id to doc1 and doc2
    anno1 = Annotation.objects.create(
        footnote=footnote1,
        content={
            **annotation.content,
            "target": {"source": {"id": f"/documents/{doc1.pk}/iiif/canvas/1/"}},
        },
    )
    anno2 = Annotation.objects.create(
        footnote=footnote1,
        content={
            **annotation.content,
            "target": {"source": {"id": f"/documents/{doc1.pk}/iiif/canvas/2/"}},
        },
    )
    anno3 = Annotation.objects.create(
        footnote=footnote2,
        content={
            **annotation.content,
            "target": {"source": {"id": f"/documents/{doc2.pk}/iiif/canvas/1/"}},
        },
    )

    cmd = Command()

    annotations = [anno1, anno2, anno3]
    result = cmd.group_by_document(annotations)

    # should be a dict keyed on document pks, ordered by pk
    assert list(result.keys()) == [doc1.pk, doc2.pk]
    # should assign annotations to the correct document pk
    assert anno1 in result[doc1.pk] and anno2 in result[doc1.pk]
    assert result[doc2.pk] == [anno3]

    # bad source id: should get added to command's `unmigrated` dict
    bad_source_id = Annotation.objects.create(
        footnote=footnote1,
        content={
            **annotation.content,
            "target": {"source": {"id": "/notmatching"}},
        },
    )
    # bad document PK: should get added to command's `unmigrated` dict
    bad_pk = 123456789
    assert not Document.objects.filter(pk=bad_pk).exists()
    bad_document_pk = Annotation.objects.create(
        footnote=footnote1,
        content={
            **annotation.content,
            "target": {"source": {"id": f"/documents/{bad_pk}/iiif/canvas/1/"}},
        },
    )
    cmd.group_by_document([bad_source_id, bad_document_pk])
    assert "/notmatching" in cmd.unmigrated["annotations"]
    assert bad_pk in cmd.unmigrated["documents"]


@pytest.mark.django_db
def test_get_last_position(source, document):
    # should return the highest schema:position for an annotation on a uri
    uri = f"/documents/{document.pk}/iiif/canvas/1/"
    footnote = Footnote.objects.create(
        source=source, content_object=document, doc_relation=Footnote.DIGITAL_EDITION
    )
    Annotation.objects.create(
        footnote=footnote,
        content={"schema:position": 5, "target": {"source": {"id": uri}}},
    )
    Annotation.objects.create(
        footnote=footnote,
        content={"schema:position": 12, "target": {"source": {"id": uri}}},
    )

    cmd = Command()
    assert cmd.get_last_position(uri) == 12

    # for a uri with no annotations, should return 0
    doc2 = Document.objects.create()
    uri = f"/documents/{doc2.pk}/iiif/canvas/1/"
    assert cmd.get_last_position(uri) == 0


@pytest.mark.django_db
def test_export_csv(tmp_path):
    cmd = Command()
    cmd.updated_documents = {
        1: {
            "annotation_count": 3,
            "had_extra_canvases": False,
            "moved_to_last_canvas": True,
        },
        2: {
            "annotation_count": 10,
            "had_extra_canvases": True,
            "moved_to_last_canvas": False,
        },
    }

    out_file = tmp_path / "report.csv"
    cmd.export_csv(str(out_file))

    with open(out_file, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # should have exactly two data rows
    assert len(rows) == 2

    # should match doc data
    row = rows[0]
    assert row["pgpid"] == "1"
    assert row["annotation_count"] == "3"
    assert row["had_extra_canvases"] == "False"
    assert row["moved_to_last_canvas"] == "True"
    assert row["url"].endswith("/documents/1/")


@pytest.mark.django_db
def test_reassign_placeholder_annotations__last_canvas(source):
    doc = Document.objects.create()
    footnote = Footnote.objects.create(
        source=source, content_object=doc, doc_relation=Footnote.DIGITAL_EDITION
    )

    # mock case with only real image textblocks
    with patch.object(
        doc,
        "iiif_images",
        return_value={
            f"/documents/{doc.pk}/iiif/canvas/1/": {},
            f"/documents/{doc.pk}/iiif/canvas/2/": {},
        },
    ):
        with patch.object(
            doc.textblock_set, "filter", return_value=doc.textblock_set.none()
        ):
            annotation = Annotation.objects.create(
                footnote=footnote,
                content={
                    "schema:position": 0,
                    "target": {"source": {"id": f"/documents/{doc.pk}/iiif/canvas/1/"}},
                },
            )

            cmd = Command()
            IndexableSignalHandler.disconnect()
            cmd.reassign_placeholder_annotations(doc, [annotation])

            # should have moved to last canvas
            assert annotation.content["target"]["source"]["id"].endswith("/canvas/2/")
            assert cmd.updated_documents[doc.pk]["annotation_count"] == 1
            assert cmd.updated_documents[doc.pk]["moved_to_last_canvas"] is True


@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
@pytest.mark.django_db
def test_reassign_placeholder_annotations__one_non_image_textblock(source):
    # only one non-image textblock
    doc = Document.objects.create()
    frag = Fragment.objects.create(shelfmark="T-S NS 1.100")
    tb = TextBlock.objects.create(document=doc, fragment=frag)
    frag_img = Fragment.objects.create(
        shelfmark="T-S NS 2.100",
        iiif_url="https://iiif.example.com/TS-NS-2.100/manifest/",
    )
    TextBlock.objects.create(document=doc, fragment=frag_img)
    footnote = Footnote.objects.create(
        source=source, content_object=doc, doc_relation=Footnote.DIGITAL_EDITION
    )
    annotation = Annotation.objects.create(
        footnote=footnote,
        content={
            "schema:position": 0,
            "target": {"source": {"id": f"/documents/{doc.pk}/iiif/canvas/1/"}},
            "body": [],
        },
    )

    # prevent network request to fake iiif url
    with patch.object(
        doc,
        "iiif_images",
        return_value={"https://iiif.example.com/TS-NS-2.100/canvas/1/": {}},
    ):
        cmd = Command()
        IndexableSignalHandler.disconnect()
        cmd.reassign_placeholder_annotations(doc, [annotation])
        # should assign to the one non-image textblock
        assert annotation.content["target"]["source"]["id"] == (
            f"/documents/{doc.pk}/iiif/textblock/{tb.pk}/canvas/1/"
        )
        assert cmd.updated_documents[doc.pk]["annotation_count"] == 1


@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
@pytest.mark.django_db
def test_reassign_placeholder_annotations__multiple_tbs(source):
    # multiple non-image textblocks
    doc = Document.objects.create()
    frag = Fragment.objects.create(shelfmark="T-S 1")
    frag_2 = Fragment.objects.create(shelfmark="ENA 1000")
    TextBlock.objects.create(document=doc, fragment=frag)
    TextBlock.objects.create(document=doc, fragment=frag_2)

    # one image textblock
    frag_3 = Fragment.objects.create(
        shelfmark="T-S NS 2.1",
        iiif_url="https://iiif.example.com/TS-NS-2.1/manifest/",
    )
    TextBlock.objects.create(document=doc, fragment=frag_3)

    # annotation on old placeholder
    footnote = Footnote.objects.create(
        source=source, content_object=doc, doc_relation=Footnote.DIGITAL_EDITION
    )
    annotation = Annotation.objects.create(
        footnote=footnote,
        content={
            "schema:position": 0,
            "target": {"source": {"id": f"/documents/{doc.pk}/iiif/canvas/1/"}},
            "body": [{"label": "Recto"}],
        },
    )

    # prevent network request to fake iiif url
    with patch.object(
        doc,
        "iiif_images",
        return_value={"https://iiif.example.com/TS-NS-2.1/canvas/1/": {}},
    ):
        cmd = Command()
        IndexableSignalHandler.disconnect()
        cmd.reassign_placeholder_annotations(doc, [annotation])

        # should add to unmigrated since we don't know which textblock to assign
        assert doc.pk in cmd.unmigrated["documents"]


@pytest.mark.django_db
def test_reassign_placeholder_annotations__extra_canvases(source):
    doc = Document.objects.create()
    frag = Fragment.objects.create(shelfmark="T-S NS 1.1")
    tb = TextBlock.objects.create(document=doc, fragment=frag)
    footnote = Footnote.objects.create(
        source=source, content_object=doc, doc_relation=Footnote.DIGITAL_EDITION
    )

    # annotation on a canvas > 2, even though we only have one fragment
    annotation = Annotation.objects.create(
        footnote=footnote,
        content={
            "schema:position": 0,
            "target": {"source": {"id": f"/documents/{doc.pk}/iiif/canvas/5/"}},
            "body": [],
        },
    )

    # should reassign canvas > 2 to 2
    cmd = Command()
    IndexableSignalHandler.disconnect()
    cmd.reassign_placeholder_annotations(doc, [annotation])
    assert annotation.content["target"]["source"]["id"].endswith(
        f"/textblock/{tb.pk}/canvas/2/"
    )
    assert cmd.updated_documents[doc.pk]["had_extra_canvases"] is True


@pytest.mark.django_db
def test_reassign_placeholder_annotations__mixed_edge_case(source):
    # create the doc with the known mixed iiif and placeholders
    doc = Document.objects.create(pk=5575)
    footnote = Footnote.objects.create(
        source=source, content_object=doc, doc_relation=Footnote.DIGITAL_EDITION
    )

    # mock case with some real image textblocks
    real_canvas = lambda i: f"http://ex.co/iiif/canvas/{i}/"
    with patch.object(
        doc,
        "iiif_images",
        return_value={real_canvas(1): {}, real_canvas(2): {}},
    ):
        # add a few annotations on the "real" iiif images (mocked)
        for i in range(3):
            Annotation.objects.create(
                footnote=footnote,
                content={
                    "schema:position": i,
                    "target": {"source": {"id": real_canvas(1)}},
                },
            )
            Annotation.objects.create(
                footnote=footnote,
                content={
                    "schema:position": i,
                    "target": {"source": {"id": real_canvas(2)}},
                },
            )

        # add an annotation on an old-style placeholder
        annotation = Annotation.objects.create(
            footnote=footnote,
            content={
                "schema:position": 0,
                "target": {"source": {"id": "/documents/5575/iiif/canvas/1/"}},
            },
        )

        cmd = Command()
        IndexableSignalHandler.disconnect()
        cmd.reassign_placeholder_annotations(doc, [annotation])

        # should get moved to the first real canvas
        assert annotation.content["target"]["source"]["id"] == real_canvas(1)
        assert cmd.updated_documents[5575]["moved_to_last_canvas"] is False
        # should be ordered last (0, 1, 2 are the existing positions)
        assert annotation.content["schema:position"] == 3


@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
@pytest.mark.django_db
def test_reassign_placeholder_annotations__known_shelfmark_edge_case(source):
    # create a document on a fragment with the shelfmark T-S NS 92.33
    doc = Document.objects.create()
    frag = Fragment.objects.create(shelfmark="T-S NS 92.33")
    tb = TextBlock.objects.create(document=doc, fragment=frag)
    # create an additional non-image fragment
    frag_2 = Fragment.objects.create(shelfmark="ENA 3765.3")
    TextBlock.objects.create(document=doc, fragment=frag_2)
    # create an image fragment
    frag_3 = Fragment.objects.create(
        shelfmark="TS-NS-2.22", iiif_url="https://iiif.example.com/TS-NS-2.22/manifest/"
    )
    TextBlock.objects.create(document=doc, fragment=frag_3)

    # annotate on the old style placeholder
    footnote = Footnote.objects.create(
        source=source, content_object=doc, doc_relation=Footnote.DIGITAL_EDITION
    )
    annotation = Annotation.objects.create(
        footnote=footnote,
        content={
            "schema:position": 0,
            "target": {"source": {"id": f"/documents/{doc.pk}/iiif/canvas/1/"}},
            # label points to T-S NS 92.33
            "body": [{"label": "TS NS 92, f. 33"}],
        },
    )

    # mock one image
    with patch.object(
        Document,
        "iiif_images",
        return_value={"https://iiif.example.com/TS-NS-2.22/canvas/1/": {}},
    ):
        cmd = Command()
        IndexableSignalHandler.disconnect()
        cmd.reassign_placeholder_annotations(doc, [annotation])

        # should assign to the correct textblock
        assert annotation.content["target"]["source"]["id"].endswith(
            f"textblock/{tb.pk}/canvas/1/"
        )
        assert cmd.updated_documents[doc.pk]["annotation_count"] == 1


@pytest.mark.django_db
def test_handle(tmp_path, capsys, source):
    # minimal document + annotation needed for command to run
    doc = Document.objects.create()
    footnote = Footnote.objects.create(
        source=source,
        content_object=doc,
        doc_relation=Footnote.DIGITAL_TRANSLATION,
    )
    Annotation.objects.create(
        footnote=footnote,
        content={
            "schema:position": 0,
            "target": {"source": {"id": f"/documents/{doc.pk}/iiif/canvas/1/"}},
        },
    )

    report_path = tmp_path / "out.csv"

    # mock all the helper functions
    with patch.object(
        Command, "group_by_document", return_value={doc.pk: ["dummy_annotation"]}
    ):
        with patch.object(Command, "reassign_placeholder_annotations"):
            with patch.object(Command, "export_csv") as mock_export:
                # simulate csv writing from export_csv
                mock_export.side_effect = lambda path: open(path, "w").write("header\n")
                # simulate unmigrated results
                with patch.object(
                    Command,
                    "unmigrated",
                    {"documents": {999}, "annotations": {"/bad/uri/"}},
                ):
                    # avoid actual reindexing
                    with patch.object(Document, "index_items"):
                        call_command("migrate_orphan_placeholders", str(report_path))

    # should write csv file
    assert report_path.exists()

    # should write to stdout
    out = capsys.readouterr().out
    assert "Reassigning annotations..." in out
    assert "Done!" in out

    # should print totals
    assert "- Total annotations updated:" in out
    assert "- Total documents affected:" in out

    # should print unmigrated
    assert "The following PGPIDs encountered errors during migration:" in out
    assert "- 999" in out
    assert "The following annotation canvas URIs could not be migrated:" in out
    assert "- /bad/uri/" in out
