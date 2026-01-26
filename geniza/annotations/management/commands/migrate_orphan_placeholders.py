import csv
import re
from collections import OrderedDict, defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.urls import reverse
from parasolr.django.signals import IndexableSignalHandler
from rich.progress import track

from geniza.annotations.models import Annotation
from geniza.common.utils import absolutize_url
from geniza.corpus.models import Document


class Command(BaseCommand):
    """One-time management command to migrate annotations from the old style of placeholders,
    which were only linked to Document ID, to the new style, which includes a TextBlock ID
    in its URI.

    /documents/{document.pk}/iiif/canvas/{canvas_number}/
    --> /documents/{document.pk}/iiif/textblock/{textblock.pk}/canvas/{canvas_number}/

    Outputs a report as a CSV with one row per document, indicating how many annotations
    were migrated, whether they were placed on existing images, and whether there were
    more than two placeholder canvases per fragment.

    Also prints any failures, and the total number of documents and annotations updated.
    """

    # track statistics
    updated_documents = defaultdict(
        lambda: {
            "annotation_count": 0,
            "had_extra_canvases": False,
            "moved_to_last_canvas": False,
        }
    )
    report_fields = [
        "pgpid",
        "annotation_count",
        "had_extra_canvases",
        "moved_to_last_canvas",
        "url",
    ]
    unmigrated = {"documents": set(), "annotations": set()}

    # regex patterns
    doc_pk_re = re.compile(r"/documents/(\d+)/")
    placeholder_url_re = re.compile(r"^(.*?/documents)/\d+/iiif/canvas/(\d+)/?$")

    def add_arguments(self, parser):
        parser.add_argument(
            "report-path",
            type=str,
            nargs="?",
            default="annotation-migration-report.csv",
        )

    def handle(self, *args, **options):
        # find all placeholders using the old style of URI, namely:
        # /documents/{document.pk}/iiif/canvas/{canvas_number}/
        old_style_placeholder_annotations = Annotation.objects.filter(
            Q(content__target__source__id__icontains="iiif/canvas")
            & Q(content__target__source__id__icontains="geniza.princeton.edu")
        ).order_by("content__schema:position", "created")

        # group anotations by document PGPID
        annotations_by_doc = self.group_by_document(old_style_placeholder_annotations)

        # disconnect solr indexing signals; this script will reindex documents manually
        IndexableSignalHandler.disconnect()

        # attempt to migrate
        for pgpid, annotations in track(
            annotations_by_doc.items(), description="Reassigning annotations..."
        ):
            document = Document.objects.get(pk=pgpid)
            self.reassign_placeholder_annotations(document, annotations)

        self.stdout.write("Reindexing documents...")
        pgpids_to_index = list(self.updated_documents.keys())
        docs_to_index = Document.objects.filter(pk__in=pgpids_to_index)
        Document.index_items(docs_to_index)

        self.stdout.write("Exporting stats CSV...")
        self.export_csv(options["report-path"])
        total_annotations = sum(
            stats["annotation_count"] for stats in self.updated_documents.values()
        )
        self.stdout.write("Done!")
        self.stdout.write("- Total annotations updated: %d" % total_annotations)
        self.stdout.write(
            "- Total documents affected: %d" % len(self.updated_documents)
        )
        if self.unmigrated["documents"]:
            self.stdout.write(
                "The following PGPIDs encountered errors during migration:"
            )
            for doc in self.unmigrated["documents"]:
                self.stdout.write("- %d" % doc)
        if self.unmigrated["annotations"]:
            self.stdout.write(
                "The following annotation canvas URIs could not be migrated:"
            )
            for canvas_uri in self.unmigrated["annotations"]:
                self.stdout.write("- %s" % canvas_uri)

    def export_csv(self, path):
        """Generate a CSV to report results, with one document per row"""
        with open(path, "w", newline="") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(self.report_fields)
            for pgpid, stats in self.updated_documents.items():
                csvwriter.writerow(
                    [
                        pgpid,
                        stats["annotation_count"],
                        stats["had_extra_canvases"],
                        stats["moved_to_last_canvas"],
                        absolutize_url(reverse("corpus:document", args=[str(pgpid)])),
                    ]
                )

    def group_by_document(self, annotations):
        """Group annotations by document PGPID, checking old PGPIDs,
        and tracking when documents could not be found."""
        annotations_by_doc = defaultdict(list)
        for annotation in track(annotations, description="Collecting annotations..."):
            match = self.doc_pk_re.search(annotation.target_source_id)
            if match:
                pgpid = int(match.group(1))
                try:
                    document = Document.objects.get_by_any_pgpid(pgpid)
                except Document.DoesNotExist:
                    self.unmigrated["documents"].add(pgpid)
                    continue
                annotations_by_doc[document.pk].append(annotation)
            else:
                self.unmigrated["annotations"].add(annotation.target_source_id)
        # order keys by PGPID
        return OrderedDict(sorted(annotations_by_doc.items()))

    def get_last_position(self, canvas_uri):
        """Get the max annotation schema:position for a given canvas URI"""
        annotations = Annotation.objects.filter(
            content__target__source__id=canvas_uri
        ).values_list("content__schema:position", flat=True)
        positions = [int(pos) for pos in annotations if pos is not None]
        return max(positions, default=0)

    def reassign_placeholder_annotations(self, document, annotations):
        """Reassign annotations on placeholders to appopriate canvases."""

        # find textblocks for fragments without images on the document
        non_image_textblocks = document.textblock_set.filter(
            Q(fragment__iiif_url__isnull=True) | Q(fragment__iiif_url="")
        )

        # handle placeholder annotations --> real iiif image
        iiif_images = document.iiif_images()

        # known edge case: mixed iiif and placeholders, but annotation header
        # includes ALL shelfmarks, so just put on first image (PGPID 5575)
        is_mixed_document = document.pk == 5575

        if not non_image_textblocks.exists() or is_mixed_document:
            # ONLY textblocks with images: use the last canvas on the document,
            # using the existing order (so that placeholder positions match
            # existing behavior)
            if iiif_images:
                # grab last canvas from document images (unless is_mixed_document)
                canvases = list(iiif_images.keys())
                canvas_uri = canvases[0] if is_mixed_document else canvases[-1]
                self.updated_documents[document.pk]["moved_to_last_canvas"] = (
                    False if is_mixed_document else True
                )
                # grab last annotation position so we can append these to the end
                last_anno_position = self.get_last_position(canvas_uri)
                for idx, annotation in enumerate(annotations, start=1):
                    # reassign to last canvas, update position
                    annotation.content["target"]["source"]["id"] = canvas_uri
                    annotation.content["schema:position"] = last_anno_position + idx
                    annotation.save()
                    self.updated_documents[document.pk]["annotation_count"] += 1
            return  # that's all we need to do here

        # handle placeholder annotations --> placeholder image
        textblock = None
        if non_image_textblocks.count() == 1 or not iiif_images:
            # only one non-image textblock, or all textblocks are non-image
            textblock = non_image_textblocks.first()

        # reassign annotations to textblock-identified placeholders
        last_positions_cache = {}
        for annotation in annotations:
            # grab base uri and canvas from original uri
            uri = annotation.target_source_id
            match = self.placeholder_url_re.match(uri)
            base_uri = match.group(1)
            canvas_number = int(match.group(2))

            # handle any that did not get a textblock
            if not textblock:
                if (
                    "label" in annotation.content["body"][0]
                    and "TS NS 92, f. 33" in annotation.content["body"][0]["label"]
                ):
                    # known edge case 2: mixed iiif and placeholders with annotations;
                    # annotation label contains shelfmark
                    textblock = document.textblock_set.get(
                        fragment__shelfmark="T-S NS 92.33"
                    )
                else:
                    self.unmigrated["documents"].add(document.pk)
                    return

            # old placeholders could have more than 2 canvases, so move all of
            # the later ones to canvas 2, and update stats
            if canvas_number > 2:
                canvas_number = 2
                self.updated_documents[document.pk]["had_extra_canvases"] = True

            # generate new placeholder URI
            new_placeholder_uri = f"{base_uri}/{document.pk}/iiif/textblock/{textblock.pk}/canvas/{canvas_number}/"

            # ensure ordering remains (cache ordering result for efficiency)
            last_anno_position = last_positions_cache.get(new_placeholder_uri)
            if last_anno_position is None:
                last_anno_position = self.get_last_position(new_placeholder_uri)
            last_positions_cache[new_placeholder_uri] = last_anno_position + 1

            # update annotation uri and stats
            annotation.content["schema:position"] = last_anno_position + 1
            annotation.content["target"]["source"]["id"] = new_placeholder_uri
            annotation.save()
            self.updated_documents[document.pk]["annotation_count"] += 1
