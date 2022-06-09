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

from geniza.corpus.models import Document
from geniza.corpus.tei_transcriptions import GenizaTei
from geniza.footnotes.models import Footnote, Source


class Command(BaseCommand):
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

        # make sure we have latest tei content from git repository
        # self.sync_git(gitrepo_url, gitrepo_path)

        self.stats = defaultdict(int)

        xmlfiles = options["files"] or glob.iglob(os.path.join(gitrepo_path, "*.xml"))

        # create factory object for constructing annotations
        manifest_factory = factory.ManifestFactory()
        # we may want this for other warnings? but warns every time about missing @id
        manifest_factory.debug_level = "info"  # suppress warning about missing id

        sas_client = AnnotationStore(settings.ANNOTATION_SERVER_URL)

        # iterate through all tei files in the repository
        for xmlfile in xmlfiles:
            self.stats["xml"] += 1
            print(xmlfile)
            xmlfile_basename = os.path.basename(xmlfile)

            tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
            # some files are stubs with no content
            # check if there is no text content; report and skip
            if tei.no_content():
                if self.verbosity >= self.v_normal:
                    self.stdout.write("%s has no text content, skipping" % xmlfile)
                self.stats["empty_tei"] += 1
                continue
            elif not tei.text.lines:
                self.stdout.write("%s has no lines (translation?), skipping" % xmlfile)
                self.stats["empty_tei"] += 1
                continue

            # get the document id from the filename (####.xml)
            pgpid = os.path.splitext(xmlfile_basename)[0]
            # in ONE case there is a duplicate id with b suffix on the second
            try:
                pgpid = int(pgpid.strip("b"))
            except ValueError:
                if self.verbosity >= self.v_normal:
                    self.stderr.write(
                        "Failed to generate integer PGPID from %s" % pgpid
                    )
                continue
            # can we rely on pgpid from xml?
            # but in some cases, it looks like a join 12047 + 12351

            # find the document in the database
            try:
                doc = Document.objects.get(
                    models.Q(id=pgpid) | models.Q(old_pgpids__contains=[pgpid])
                )
            except Document.DoesNotExist:
                self.stats["document_not_found"] += 1
                if self.verbosity >= self.v_normal:
                    self.stdout.write("Document %s not found in database" % pgpid)
                continue

            # found the document
            print(doc)
            # if there is a single primary language, use the iso code if it is set
            lang_code = None
            if doc.languages.count() == 1:
                lang_code = doc.languages.first().iso_code

            # get html chunked roughly by page from the tei
            # TODO: will need separate annotations within page for labeled text
            # NOTE: maybe we want to get the blocks that are generated internally instead
            html_chunks = tei.text_to_html()

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
                "%s html chunks and %s canvases"
                % (len(html_chunks), len(iiif_canvases))
            )

            # NOTE: pgpid 1390 folio example; each chunk should be half of the canvas
            if len(html_chunks) > len(iiif_canvases):
                self.stdout.write(
                    "%s has more html chunks than canvases; skipping" % xmlfile
                )
                continue

            for i, html in enumerate(html_chunks):
                # get corresponding canvas for this section of text (assuming sequences match)
                # canvas includes canvas id, image id, width, height
                canvas = iiif_canvases[i]

                # for now, remove existing annotations for this canvas so we can reimport as needed
                existing_annos = sas_client.search(str(canvas.image.info()))
                print(
                    "Removing %s existing annotation(s) for %s"
                    % (len(existing_annos), canvas.image.info())
                )
                for anno in existing_annos:
                    sas_client.delete(anno["@id"])

                # create a new annotation; working with v2 because that's what SAS supports
                # don't set an id; allow SAS to generate ids on save
                anno = manifest_factory.annotation()
                # supplement rather than painting over the image
                # multiple motivations are allowed; add transcription as secondary motivation
                anno.motivation = ["sc:supplementing", "ext:transcription"]
                # document the annotation target ("on")
                # NOTE: currently using image id; switch to canvas id here once we switch in the editor
                anno.add_canvas(
                    "%s#xywh=0,0,%s,%s"
                    % (canvas.image.info(), canvas.width, canvas.height)
                )
                anno.within = {
                    "@type": "sc:Manifest",
                    "@id": settings.ANNOTATION_MANIFEST_BASE_URL
                    + reverse(
                        "corpus:document-manifest", args=[doc.pk]
                    ),  # "https://geniza.princeton.edu/en/documents/2806/iiif/manifest/",
                }

                # create text body; specify language if known
                anno.text(html, format="text/html", language=lang_code)
                # can we save arbitrary metadata?
                anno.resource.motivation = "transcription"
                anno.resource.label = "test Label"
                # explicitly indicate text direction; all of our transcriptions are rtl
                # but NOTE: SAS doesn't seem to be preserving text direction (maybe not a v2 feature)
                anno.resource.textDirection = "rtl"
                # we can set arbitrary metadata that SAS will preserve as long as we namespace our properties
                setattr(anno, "oa:annotatedBy", "username")
                setattr(anno, "ext:order", i + 1)
                setattr(anno, "ext:scholarshiprecord", "footnote/source uri")

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
