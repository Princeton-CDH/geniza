"""
Script to convert transcription content from PGP v3 TEI files
to IIIF annotations in the configured annotation server.

"""

import glob
import os.path
from collections import defaultdict
from datetime import datetime

import requests
from addict import Dict
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from eulxml import xmlmap
from git import Repo
from parasolr.django.signals import IndexableSignalHandler
from rest_framework.authtoken.models import Token

from geniza.annotations.models import Annotation
from geniza.common.utils import absolutize_url
from geniza.corpus.management.commands import sync_transcriptions
from geniza.corpus.models import Document
from geniza.corpus.tei_transcriptions import GenizaTei
from geniza.footnotes.models import Footnote


class Command(sync_transcriptions.Command):
    """Synchronize TEI transcriptions to edition footnote content"""

    v_normal = 1  # default verbosity

    missing_footnotes = []

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
        # get content type and script nuser for log entries
        self.footnote_contenttype = ContentType.objects.get_for_model(Footnote)
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()
        # NOTE: can't disconnect annotation signal handler because it
        # is server side and we're accessing via API

        # make sure we have latest tei content from git repository
        # (inherited from sync transcriptions command)
        self.sync_git(gitrepo_url, gitrepo_path)

        self.stats = defaultdict(int)

        xmlfiles = options["files"] or glob.iglob(os.path.join(gitrepo_path, "*.xml"))

        annotation_client = AnnotationStore(auth_token=token.key)

        script_run_start = timezone.now()

        # when running on all files (i.e., specific files not specified),
        # clear all annotations from the database before running the migration
        # NOTE: could make this optional behavior, but it probably only
        # impacts development and not the real migration?
        if not options["files"]:
            # cheating a little here, but much faster to clear all at once
            # instead of searching and deleting one at a time
            all_annos = Annotation.objects.all()
            self.stdout.write("Clearing %d annotations" % all_annos.count())
            all_annos.delete()

        # iterate through tei files to be migrated
        for xmlfile in xmlfiles:
            self.stats["xml"] += 1
            if self.verbosity >= self.v_normal:
                self.stdout.write(xmlfile)

            xmlfile_basename = os.path.basename(xmlfile)

            tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
            # some files are stubs with no content
            # check if the tei is ok to proceed; (e.g., empty or only translation content)
            # if empty, report and skip
            if not self.check_tei(tei, xmlfile):
                self.stdout.write(
                    self.style.WARNING(
                        "No transcription content in %s; skipping" % xmlfile
                    )
                )
                continue
            # get the document for the file based on id / old id
            doc = self.get_pgp_document(xmlfile_basename)
            # if document was not found, skip
            if not doc:
                self.stdout.write(
                    self.style.WARNING("Document not found for %s; skipping" % xmlfile)
                )
                continue
            # found the document
            if self.verbosity >= self.v_normal:
                self.stdout.write(str(doc))

            # get the footnote for this file & doc
            footnote = self.get_edition_footnote(doc, tei, xmlfile)
            # if no footnote, skip for now
            # TODO: generate footnote when needed! (but should we need to?)
            if not footnote:
                self.stdout.write(
                    self.style.ERROR(
                        "footnote not found for %s / %s; skipping" % (xmlfile, doc.pk)
                    )
                )
                self.missing_footnotes.append(xmlfile)
                continue
            footnote = self.migrate_footnote(footnote, doc)

            # if there is a single primary language, use the iso code if it is set
            lang_code = None
            if doc.languages.count() == 1:
                lang_code = doc.languages.first().iso_code

            # get html blocks from the tei
            html_blocks = tei.text_to_html(block_format=True)

            # get canvas objects for the images in order; skip any non-document images
            iiif_canvases = [img["canvas"] for img in doc.iiif_images(filter_side=True)]
            # determine the number of canvases needed based on labels
            # that indicate new pages
            # check and count any after the first; always need at least 1 canvas
            num_canvases = 1 + len(
                [
                    b["label"]
                    for b in html_blocks[1:]
                    if tei.label_indicates_new_page(b["label"])
                ]
            )
            # in verbose mode report on available/needed canvases
            if self.verbosity > self.v_normal:
                self.stdout.write(
                    "%d iiif canvases; need %d canvases for %d blocks"
                    % (len(iiif_canvases), num_canvases, len(html_blocks))
                )
            # if we need more canvases than we have available,
            # generate local canvas ids
            if num_canvases > len(iiif_canvases):
                # document manifest url is /documents/pgpid/iiif/manifest/
                # create canvas uris parallel to that
                canvas_base_uri = doc.manifest_uri.replace("manifest", "canvas")
                for i in range(num_canvases - len(iiif_canvases)):
                    canvas_uri = "%s%d/" % (canvas_base_uri, i + 1)
                    iiif_canvases.append(canvas_uri)

            # NOTE: pgpid 1390 folio example; each chunk should be half of the canvas
            # (probably should be handled manually)
            # if len(html_chunks) > len(iiif_canvases):
            #     self.stdout.write(
            #         "%s has more html chunks than canvases; skipping" % xmlfile
            #     )
            #     continue

            # start attaching to first canvas; increment based on chunk label
            canvas_index = 0

            # if specific files were specified, remove annotations
            # just for those documents & sources
            if options["files"]:
                # remove all existing annotations associated with this
                # document and source so we can reimport as needed
                existing_annos = annotation_client.search(
                    source=footnote.source.uri, manifest=doc.manifest_uri
                )
                # FIXME: this is probably problematic for transcriptions currently
                # split across two TEi files...
                # maybe filter by date created also, so we only remove
                # annotations created before the current script run?

                num_before = len(existing_annos)
                # filter to annotations created before current script run
                existing_annos = [
                    a
                    for a in existing_annos
                    if datetime.fromisoformat(a["created"]) < script_run_start
                ]
                # for debugging, report if this differs
                if len(existing_annos) != num_before:
                    print(
                        "%d existing annotations before current script run (%d total)"
                        % (len(existing_annos), num_before)
                    )

                if existing_annos:
                    print(
                        "Removing %s existing annotation(s) for %s on %s "
                        % (len(existing_annos), footnote.source, doc.manifest_uri)
                    )
                    for anno in existing_annos:
                        annotation_client.delete(anno["id"])

            for i, block in enumerate(html_blocks):
                # if this is not the first block and the label suggests new image,
                # increment canvas index
                if i != 0 and tei.label_indicates_new_page(block["label"]):
                    canvas_index += 1

                # get the canvas uri for this section of text
                annotation_target = iiif_canvases[canvas_index]

                anno = new_transcription_annotation()
                # link to digital edition footnote via source URI
                anno["dc:source"] = footnote.source.uri

                anno.target.source.id = annotation_target
                anno.target.source.partOf.type = "Manifest"
                anno.target.source.partOf.id = doc.manifest_uri

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

                # print(anno) # can print for debugging

                created = annotation_client.create(anno)
                if created:
                    self.stats["created"] += 1

        print(
            "Processed %(xml)d TEI file(s). \nCreated %(created)d annotation(s)."
            % self.stats
        )

        # report on missing footnotes
        if self.missing_footnotes:
            print(
                "Could not find footnotes for %s documents:"
                % len(self.missing_footnotes)
            )
            for xmlfile in self.missing_footnotes:
                print("\t%s" % xmlfile)

    def get_footnote_editions(self, doc):
        # extend to return digital edition or edition
        # (digital edition if from previous run of this script)
        return doc.footnotes.filter(
            models.Q(doc_relation__contains=Footnote.EDITION)
            | models.Q(doc_relation__contains=Footnote.DIGITAL_EDITION)
        )

    # we shouldn't be creating new footnotes at this point...
    # override method from sync transcriptions to ensure we don't
    def is_it_goitein(self, tei, doc):
        return None

    def migrate_footnote(self, footnote, document):
        # convert existing edition footnote to digital edition
        # OR make a new one if the existing footnote has other information

        # convert existing edition footnote to digital edition
        # OR make a new one if the existing footnote has other information

        # if footnote is already a digital edition, nothing to be done
        # (already migrated in a previous run)
        if footnote.doc_relation == Footnote.DIGITAL_EDITION:
            return footnote

        # if footnote has other types or a url, we should preserve it
        if (
            set(footnote.doc_relation).intersection(
                {Footnote.TRANSLATION, Footnote.DISCUSSION}
            )
            or footnote.url
            or footnote.location
        ):
            # remove interim transcription content
            if footnote.content:
                footnote.content = None
                footnote.save()

            # if a digital edition footnote for this document+source exists,
            # use that instead of creating a duplicate
            diged_footnote = document.footnotes.filter(
                doc_relation=Footnote.DIGITAL_EDITION, source=footnote.source
            ).first()
            if diged_footnote:
                return diged_footnote

            # otherwise, make a new one
            new_footnote = Footnote(
                doc_relation=Footnote.DIGITAL_EDITION, source=footnote.source
            )
            # trying to set from related object footnote.document errors
            new_footnote.content_object = document
            new_footnote.save()
            log_action = ADDITION
            log_message = "Created new footnote for migrated digital edition"

            # assign to footnote for logging and return
            footnote = new_footnote

        else:
            # otherwise, convert edition to digital edition
            footnote.doc_relation = Footnote.DIGITAL_EDITION
            footnote.content = ""
            footnote.save()

            log_action = CHANGE
            log_message = "Migrated footnote to digital edition"

        # log entry to document footnote the change
        LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=self.footnote_contenttype.pk,
            object_id=footnote.pk,
            object_repr=str(footnote),
            change_message=log_message,
            action_flag=log_action,
        )
        return footnote


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