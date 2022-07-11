"""
Script to convert transcription content from PGP v3 TEI files
to IIIF annotations in the configured annotation server.

"""

import glob
import os.path
from collections import defaultdict

import requests
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.urls import reverse
from eulxml import xmlmap
from git import Repo
from iiif_prezi import factory

from geniza.corpus.management.commands import sync_transcriptions
from geniza.corpus.models import Document
from geniza.corpus.tei_transcriptions import GenizaTei


class Command(sync_transcriptions.Command):
    """Synchronize TEI transcriptions to edition footnote content"""

    v_normal = 1  # default verbosity

    def add_arguments(self, parser):
        parser.add_argument(
            "files", nargs="*", help="Only convert the specified files."
        )

    def handle(self, *args, **options):
        # get settings for remote git repository url and local path
        gitrepo_url = settings.TEI_TRANSCRIPTIONS_GITREPO
        gitrepo_path = settings.TEI_TRANSCRIPTIONS_LOCAL_PATH

        self.verbosity = options["verbosity"]

        # NOTE: some overlap with sync transcriptions manage command

        # make sure we have latest tei content from git repository
        # (inherited from sync transcriptions command)
        self.sync_git(gitrepo_url, gitrepo_path)

        self.stats = defaultdict(int)

        xmlfiles = options["files"] or glob.iglob(os.path.join(gitrepo_path, "*.xml"))

        # create factory object for constructing annotations
        manifest_factory = factory.ManifestFactory()
        # we may want this for other warnings? but warns every time about missing @id
        manifest_factory.debug_level = "info"  # suppress warning about missing id

        sas_client = AnnotationStore(settings.ANNOTATION_SERVER_URL)

        # iterate through tei files to be migrated
        for xmlfile in xmlfiles:
            self.stats["xml"] += 1
            print(xmlfile)
            xmlfile_basename = os.path.basename(xmlfile)

            tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
            # some files are stubs with no content
            # check if the tei is ok to proceed; (e.g., empty or only translation content)
            # if empty, report and skip
            if not self.check_tei(tei, xmlfile):
                continue
            # get the document for the file based on id / old id
            doc = self.get_pgp_document(xmlfile_basename)
            # if document was not found, skip
            if not doc:
                continue

            # found the document
            print(doc)
            # if there is a single primary language, use the iso code if it is set
            lang_code = None
            if doc.languages.count() == 1:
                lang_code = doc.languages.first().iso_code

            # get html blocks from the tei
            html_blocks = tei.text_to_html(block_format=True)

            # get canvas objects for the images
            iiif_canvases = []
            for b in doc.textblock_set.all():
                # TODO: add placeholder canvas ids for documents without iiif
                if b.fragment.manifest:
                    # TODO: only include canvases this document is on, per side information (recto/verso)
                    iiif_canvases.extend(b.fragment.manifest.canvases.all())
                else:
                    print("no manifest for %s" % b.fragment)

            print(
                "%s html blocks and %s canvases"
                % (len(html_blocks), len(iiif_canvases))
            )

            # NOTE: pgpid 1390 folio example; each chunk should be half of the canvas
            # if len(html_chunks) > len(iiif_canvases):
            #     self.stdout.write(
            #         "%s has more html chunks than canvases; skipping" % xmlfile
            #     )
            #     continue

            # start attaching to first canvas; increment based on chunk label
            canvas_index = 0

            for i, block in enumerate(html_blocks):
                # if this is not the first block and the label suggests new image,
                # increment canvas index
                if i != 0 and tei.label_indicates_new_page(block["label"]):
                    canvas_index += 1

                # get the canvas for this section of text
                # canvas includes canvas id, image id, width, height
                canvas = iiif_canvases[canvas_index]

                annotation_target = canvas.uri
                # previously image url
                # annotation_target = str(canvas.image.info())

                # for now, remove existing annotations for this canvas so we can reimport as needed
                # TODO: clear all canvases once before adding? how to avoid clearing out alt. transcriptions?
                existing_annos = sas_client.search(annotation_target)
                print(
                    "Removing %s existing annotation(s) for %s"
                    % (len(existing_annos), annotation_target)
                )
                for anno in existing_annos:
                    sas_client.delete(anno["@id"])

                # create a new annotation; working with v2 because that's what SAS supports
                # don't set an id; allow SAS to generate ids on save
                anno = manifest_factory.annotation()
                # supplement rather than painting over the image
                # multiple motivations are allowed; add transcription as secondary motivation
                anno.motivation = ["sc:supplementing", "ext:transcription"]
                # document the annotation target ("on");
                # apply to the full canvas using % notation
                # (using nearly full canvas to make it easier to edit zones)
                anno.add_canvas(
                    "%s#percent:1,1,98,98"
                    % (annotation_target,)
                    # previously "%s#xywh=0,0,%s,%s" using canvas width & height
                )
                anno.within = {
                    "@type": "sc:Manifest",
                    "@id": settings.ANNOTATION_MANIFEST_BASE_URL
                    + reverse(
                        "corpus:document-manifest", args=[doc.pk]
                    ),  # "https://geniza.princeton.edu/en/documents/2806/iiif/manifest/",
                }

                # create text body; specify language if known
                html = " <ul>%s</ul>" % "".join(
                    "\n <li%s>%s</li>"
                    % (f" value='{line_number}'" if line_number else "", line)
                    for line_number, line in block["lines"]
                    if line.strip()
                )
                anno.text(html, format="text/html", language=lang_code)
                # can we save arbitrary metadata?
                anno.resource.motivation = "transcription"
                anno.resource.label = block["label"]
                # explicitly indicate text direction; all of our transcriptions are rtl
                # but NOTE: SAS doesn't seem to be preserving text direction (maybe not a v2 feature)
                anno.resource.textDirection = "rtl"
                # we can set arbitrary metadata that SAS will preserve as long as we namespace our properties
                # setattr(anno, "oa:annotatedBy", "username")
                setattr(anno, "ext:order", i + 1)
                # setattr(anno, "ext:scholarshiprecord", "footnote/source uri")

                # print(anno.toJSON())

                created = sas_client.create(anno)
                if created:
                    self.stats["created"] += 1

        print(
            "Processed %(xml)d TEI file(s). \nCreated %(created)d annotation(s)."
            % self.stats
        )


class AnnotationStore:
    def __init__(self, annotation_server_url):
        self.base_url = annotation_server_url
        self.session = requests.session()  # any headers we want to set?

    def create(self, anno):
        response = self.session.post("%s/create" % self.base_url, json=anno.toJSON())
        if response.status_code == requests.codes.created:
            return True
        else:
            response.raise_for_status()

    def delete(self, anno_uri):
        response = self.session.delete(
            "%s/destroy" % (self.base_url,), params={"uri": anno_uri}
        )
        # simple annotation server returns no content either way, whether something was deleted or not...
        # raise if there's an error, otherwise assume it worked
        response.raise_for_status()

    def search(self, uri):
        response = self.session.get("%s/search" % self.base_url, params={"uri": uri})
        if response.status_code == requests.codes.ok:
            return response.json()
