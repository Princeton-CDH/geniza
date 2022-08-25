"""
Script to convert transcription content from PGP v3 TEI files
to IIIF annotations in the configured annotation server.

"""

import glob
import os.path
from collections import defaultdict

import requests
from addict import Dict
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.urls import reverse
from eulxml import xmlmap
from git import Repo
from rest_framework.authtoken.models import Token

from geniza.common.utils import absolutize_url
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

        # generate or retrieve a token for script user to use for token-auth
        token = Token.objects.get_or_create(
            user=User.objects.get(username=settings.SCRIPT_USERNAME)
        )[0]

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

        annotation_client = AnnotationStore(auth_token=token.key)

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

            # get the footnote for this file & doc
            footnote = self.get_edition_footnote(doc, tei, xmlfile)
            print(footnote)

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

            # remove all existing annotations associated with this
            # document and source so we can reimport as needed
            existing_annos = annotation_client.search(
                source=footnote.source.uri, manifest=document.manifest_uri
            )
            # FIXME: this is probably problematic for transcriptions currently
            # split across two TEi files...
            # maybe filter by date created also, so we only remove
            # annotations created before the current script run?
            if existing_annos:
                print(
                    "Removing %s existing annotation(s) for %s on %s "
                    % (len(existing_annos), footnote.source, document.manifest_uri)
                )
                for anno in existing_annos:
                    annotation_client.delete(anno["id"])

            for i, block in enumerate(html_blocks):
                # if this is not the first block and the label suggests new image,
                # increment canvas index
                if i != 0 and tei.label_indicates_new_page(block["label"]):
                    print("label %s indicates new page" % block["label"])
                    canvas_index += 1

                # get the canvas for this section of text
                # canvas includes canvas id, image id, width, height
                canvas = iiif_canvases[canvas_index]
                annotation_target = canvas.uri

                anno = new_transcription_annotation()
                # link to digital edition footnote via source URI
                anno["dc:source"] = footnote.source.uri

                anno.target.source.id = annotation_target
                anno.target.source.partOf.type = "Manifest"
                anno.target.source.partOf.id = document.manifest_uri

                # apply to the full canvas using % notation
                # (using nearly full canvas to make it easier to edit zones)
                anno.target.selector.value = "xywh=percent:1,1,98,98"
                # anno.selector.value = "%s#xywh=pixel:0,0,%s,%s" % (annotation_target, canvas.width, canvas.height)

                # add html and optional label to annotation text body
                # TODO: specify language in html if known
                anno.body[0].value = tei.lines_to_html(block["lines"])
                if block["label"]:
                    anno.body[0].label = block["label"]

                anno["schema:position"] = i + 1

                print(anno)

                created = annotation_client.create(anno)
                if created:
                    self.stats["created"] += 1

        print(
            "Processed %(xml)d TEI file(s). \nCreated %(created)d annotation(s)."
            % self.stats
        )


def new_transcription_annotation():
    # initialize a new annotation dict object with all the defaults set

    anno = Dict()
    setattr(anno, "@context", "http://www.w3.org/ns/anno.jsonld")
    anno.type = "Annotation"
    anno.body = [Dict()]
    anno.body[0].type = "TextualBody"
    anno.body[0].purpose = "transcribing"
    anno.body[0].format = "text/html"
    # explicitly indicate text direction; all transcriptions are RTL
    anno.body[0].TextInput = "rtl"
    # supplement rather than painting over the image
    # multiple motivations are allowed; add transcription as secondary motivation
    anno.motivation = ["sc:supplementing", "ext:transcription"]

    anno.target.source.type = "Canvas"
    anno.target.selector.type = "FragmentSelector"
    anno.target.selector.conformsTo = "http://www.w3.org/TR/media-frags/"

    return anno


class AnnotationStore:
    # TODO: migration for script user perms (figure out minimum permissions)
    # script account needs active, staff, and content editor permissions ?
    # (maybe...)

    def __init__(self, auth_token):
        self.base_url = absolutize_url(reverse("annotations:list"))
        self.search_url = absolutize_url(reverse("annotations:search"))
        self.session = requests.session()
        # add authentication token to session headers
        self.session.headers.update({"Authorization": "Token %s" % auth_token})

        # Request site homepage to get a CSRF token,
        # since annotation urls are currently csrf-protected.
        response = self.session.get(absolutize_url("/"))
        assert response.status_code == 200
        # set csrf token header
        self.session.headers.update({"X-CSRFToken": response.cookies["csrftoken"]})

    def create(self, anno):
        response = self.session.post(self.base_url, json=anno)
        if response.status_code == requests.codes.created:
            return True
        else:
            response.raise_for_status()

    def delete(self, anno_uri):
        response = self.session.delete(anno_uri)
        # raise if there's an error, otherwise assume it worked
        response.raise_for_status()

    def search(self, uri=None, source=None, manifest=None):
        search_opts = {}
        if uri:
            search_opts["uri"] = uri
        if source:
            search_opts["source"] = source
        if manifest:
            search_opts["manifest"] = manifest
        response = self.session.get(self.search_url, params=search_opts)
        # returns an annotation list with a list of resources
        if response.status_code == requests.codes.ok:
            return response.json()["resources"]
