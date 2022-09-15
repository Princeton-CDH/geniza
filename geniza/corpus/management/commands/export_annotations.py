import json
import os
from collections import defaultdict
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils.text import slugify

from geniza.annotations.models import Annotation, annotations_to_list
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote


class Command(BaseCommand):
    """Backup annotation data and synchronize to GitHub"""

    v_normal = 1  # default verbosity

    def handle(self, *args, **options):
        if not getattr(settings, "ANNOTATION_BACKUP_PATH"):
            raise CommandError(
                "Please configure ANNOTATION_BACKUP_PATH in django settings"
            )

        annotations_output_dir = os.path.join(
            settings.ANNOTATION_BACKUP_PATH, "annotations"
        )
        # define paths and ensure directories exist for compiled transcription
        transcription_output_dir = {}
        for output_format in ["txt", "html"]:
            format_path = os.path.join(
                settings.ANNOTATION_BACKUP_PATH, "transcriptions", output_format
            )
            transcription_output_dir[output_format] = format_path
            os.makedirs(format_path, exist_ok=True)

        # identify content to backup based on documents with digital editions
        docs = Document.objects.filter(
            footnotes__doc_relation__contains=Footnote.DIGITAL_EDITION
        ).distinct()
        self.stdout.write(
            "Backing up annotations for %d documents with digital editions"
            % docs.count()
        )
        for document in docs[:3]:
            print(document)
            # use PGPID for annotation directory name
            # path based on recommended uri pattern from the spec
            # {prefix}/{identifier}/list/{name}
            output_dir = os.path.join(annotations_output_dir, str(document.id), "list")
            # ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # find all annotations for this document
            annos = Annotation.objects.filter(
                content__target__source__partOf__id=document.manifest_uri
            )
            # TODO: ensure ordered by position / date created
            # (updated from latest view logic)

            # aggregate annotations by canvas id
            # for annotation list backup, we don't need to segment
            # by motivation, source, etc; just group by canvas
            annos_by_canvas = defaultdict(list)
            for a in annos:
                annos_by_canvas[a.target_source_id].append(a)

            # create and save one AnnotationList per canvas
            # with all associated annotations, as a backup
            # that could be imported into any w3c annotation server

            for canvas, annotations in annos_by_canvas.items():
                annolist_name = self.annotation_list_name(canvas)
                annolist_out_path = os.path.join(output_dir, "%s.json" % annolist_name)
                with open(annolist_out_path, "w") as outfile:
                    json.dump(
                        annotations_to_list(annotations, uri="test"), outfile, indent=2
                    )

            # for convenience and more readable versioning, also generate
            # text and html transcription files
            for edition in document.digital_editions():
                print(edition, edition.source)
                # filename based on pgpid and source authors;
                # explicitly label as transcription for context
                base_filename = self.transcription_filename(document, edition.source)
                for output_format in ["txt", "html"]:
                    # put in the appropriate transription dir by format,
                    # use format as file extension
                    outfile_path = os.path.join(
                        transcription_output_dir[output_format],
                        "%s.%s" % (base_filename, output_format),
                    )
                    print(outfile_path)
                    # TODO: use a minimual django template here;
                    # should include full citation for the source + footnote.

                    # FIXME: where should primary language lang code be set,
                    # for this export and for transcription on site?

                    with open(outfile_path, "w") as outfile:
                        if output_format == "html":
                            context = {"document": document, "edition": edition}
                            content = render_to_string(
                                "corpus/transcription_export.html", context
                            )
                            outfile.write(content)
                        else:
                            # TODO: template for this also?
                            # need to include source citation
                            # and line numbers for ol list items
                            outfile.write(edition.content_text)

    def annotation_list_name(self, canvas_uri):
        # per annotation spec, annotation list name must uniquely distinguish
        # it from  all other lists, and is typically the same name as the canvas.

        # canvas uris vary depending on source:
        # https://cudl.lib.cam.ac.uk/iiif/MS-TS-NS-00321-00008/canvas/1
        # https://figgy.princeton.edu/concern/scanned_resources/f9eb5730-035c-420a-bf42-13190f97c10d/manifest/canvas/cfd65bb6-7ff5-47e8-9e92-29dd0e05baf2
        # https://princetongenizalab.github.io/iiif-bodleian-a/manifests/canvas/1.json
        # https://digi.ub.uni-heidelberg.de/diglit/iiif/codheidorient78/canvas/0001

        parsed_url = urlparse(canvas_uri)

        # in most cases, we can use first portion of hostname to identify source
        # (cudl, figgy, princetongenizalab)
        if "heidelberg" in parsed_url.hostname:
            prefix = "heidelberg"
        else:
            prefix = parsed_url.hostname.split(".")[0]

        # figgy uses uuids; canvas id is last portion of path and is reliably unique
        if "figgy" in parsed_url.hostname:
            path = parsed_url.path.split("/")[0]
        else:
            # otherwise use the portion of the path after any iiif prefix
            # or full path if it does not include /iiif/
            path = parsed_url.path.partition("/iiif/")[2] or parsed_url.path
            # replace / with _ (not - since cudl manifest ids use -)
            path = path.replace("/", "_")

        # TODO: handle local PGP placeholder canvas uris
        return "_".join([prefix, path])

    def transcription_filename(self, document, source):
        # filename based on pgpid and source authors;
        # explicitly label as transcription for context
        authors = [a.creator.last_name for a in source.authorship_set.all()] or [
            "unknown author"
        ]

        return "PGPID-%s_%s_transcription" % (
            document.id,
            slugify(" ".join(authors)),
        )
