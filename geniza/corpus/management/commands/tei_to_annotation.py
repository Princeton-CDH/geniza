"""
Script to convert transcription content from PGP v3 TEI files
to IIIF annotations in the configured annotation server.

"""

import glob
import os.path
import unicodedata
from collections import defaultdict
from datetime import datetime
from functools import cached_property

import requests
from addict import Dict
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.utils import timezone
from eulxml import xmlmap
from git import Repo
from parasolr.django.signals import IndexableSignalHandler
from rich.progress import MofNCompleteColumn, Progress

from geniza.annotations.models import Annotation
from geniza.annotations.signals import disconnect_signal_handlers
from geniza.common.utils import absolutize_url
from geniza.corpus.annotation_export import AnnotationExporter
from geniza.corpus.management.commands import sync_transcriptions
from geniza.corpus.models import Document
from geniza.corpus.tei_transcriptions import GenizaTei
from geniza.footnotes.models import Footnote


class Command(sync_transcriptions.Command):
    """Synchronize TEI transcriptions to edition footnote content"""

    v_normal = 1  # default verbosity

    missing_footnotes = []

    normalized_unicode = set()

    document_not_found = []

    def add_arguments(self, parser):
        parser.add_argument(
            "files", nargs="*", help="Only convert the specified files."
        )

    def handle(self, *args, **options):
        # get settings for remote git repository url and local path
        gitrepo_url = settings.TEI_TRANSCRIPTIONS_GITREPO
        gitrepo_path = settings.TEI_TRANSCRIPTIONS_LOCAL_PATH

        self.verbosity = options["verbosity"]
        # get content type and script user for log entries
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()
        # disconnect annotation signal handlers
        disconnect_signal_handlers()

        # make sure we have latest tei content from git repository
        # (inherited from sync transcriptions command)
        self.sync_git(gitrepo_url, gitrepo_path)
        # initialize local git repo client
        self.tei_gitrepo = Repo(gitrepo_path)

        self.stats = defaultdict(int)

        xmlfiles = options["files"] or glob.glob(os.path.join(gitrepo_path, "*.xml"))
        script_run_start = timezone.now()

        self.stdout.write("Migrating %d TEI files" % len(xmlfiles))

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

        # initialize annotation exporter; don't push changes until the end;
        # commit message will be overridden per export to docment TEI file
        self.anno_exporter = AnnotationExporter(
            stdout=self.stdout,
            verbosity=options["verbosity"],
            push_changes=False,
            commit_msg="PGP transcription export from TEI migration",
        )
        self.anno_exporter.setup_repo()

        # use rich progressbar without context manager
        progress = Progress(
            MofNCompleteColumn(), *Progress.get_default_columns(), expand=True
        )
        progress.start()
        task = progress.add_task("Migrating...", total=len(xmlfiles))

        # iterate through tei files to be migrated
        for xmlfile in xmlfiles:
            self.stats["xml"] += 1
            # update progress at the beginning instead of end,
            # since some records are skipped
            progress.update(task, advance=1, update=True)

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
                self.document_not_found.append(xmlfile)
                continue
            # found the document
            if self.verbosity >= self.v_normal:
                self.stdout.write(str(doc))

            # get the footnote for this file & doc
            footnote = self.get_edition_footnote(doc, tei, xmlfile)
            # if no footnote, skip for now
            # (some are missing, but will handle with data work)
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
            iiif_canvases = list(doc.iiif_images(filter_side=True).keys())
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
                existing_annos = Annotation.objects.filter(
                    footnote__source=footnote.source,
                    footnote__content_object=doc,
                    created__lt=script_run_start,
                )
                # NOTE: this is problematic for transcriptions currently
                # split across two TEI files... take care when running
                # on individual or groups of files
                if existing_annos:
                    print(
                        "Removing %s pre-existing annotation%s for %s on %s "
                        % (
                            len(existing_annos),
                            pluralize(existing_annos),
                            footnote.source,
                            doc.manifest_uri,
                        )
                    )
                    # not creating log entries for deletion, but
                    # this should probably only come up in dev runs
                    existing_annos.delete()

            for i, block in enumerate(html_blocks):
                # if this is not the first block and the label suggests new image,
                # increment canvas index
                if i != 0 and tei.label_indicates_new_page(block["label"]):
                    canvas_index += 1

                anno = new_transcription_annotation()
                # get the canvas uri for this section of text
                annotation_target = iiif_canvases[canvas_index]
                anno.target.source.id = annotation_target

                # apply to the full canvas using % notation
                # (using nearly full canvas to make it easier to edit zones)
                anno.target.selector.value = "xywh=percent:1,1,98,98"
                # anno.selector.value = "%s#xywh=pixel:0,0,%s,%s" % (annotation_target, canvas.width, canvas.height)

                # add html and optional label to annotation text body
                # NOTE: not specifying language in html here because we
                # handle it in wrapping template code based on db language

                html = tei.lines_to_html(block["lines"])
                if not unicodedata.is_normalized("NFC", html):
                    self.normalized_unicode.add(xmlfile)
                    html = unicodedata.normalize("NFC", html)
                anno.body[0].value = html

                if block["label"]:
                    # check if label text requires normalization
                    if not unicodedata.is_normalized("NFC", block["label"]):
                        self.normalized_unicode.add(xmlfile)
                        block["label"] = unicodedata.normalize("NFC", block["label"])
                    anno.body[0].label = block["label"]

                anno["schema:position"] = i + 1
                # print(anno) # can print for debugging

                # create database annotation
                db_anno = Annotation()
                db_anno.set_content(dict(anno))
                # link to digital edition footnote
                db_anno.footnote = footnote
                db_anno.save()
                # log entry to document annotation creation
                self.log_addition(db_anno, "Migrated from TEI transcription")
                self.stats["created"] += 1

            # export migrated transcription to backup
            self.export_transcription(doc, xmlfile_basename)

        progress.refresh()
        progress.stop()

        print(
            "Processed %(xml)d TEI file(s). \nCreated %(created)d annotation(s)."
            % self.stats
        )

        # push all changes from migration to github
        self.anno_exporter.sync_github()

        # report on missing footnotes
        if self.missing_footnotes:
            print(
                "Could not find footnotes for %s document%s:"
                % (len(self.missing_footnotes), pluralize(self.missing_footnotes))
            )
            for xmlfile in self.missing_footnotes:
                print("\t%s" % xmlfile)

        # report on unicode normalization
        if self.normalized_unicode:
            print(
                "Normalized unicode for %s document%s:"
                % (len(self.normalized_unicode), pluralize(self.normalized_unicode))
            )
            for xmlfile in self.normalized_unicode:
                print("\t%s" % xmlfile)

        if self.document_not_found:
            print(
                "Document not found for %s TEI file%s:"
                % (len(self.document_not_found), pluralize(self.document_not_found))
            )
            for xmlfile in self.normalized_unicode:
                print("\t%s" % xmlfile)

        # report on edition footnotes that still have content
        # (skip when unning on a specified files)
        if not options["files"]:
            self.check_unmigrated_footnotes()

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

        # check if a digital edition footnote for this document+source exists,
        # so we can avoid creating a duplicate
        diged_footnote = document.footnotes.filter(
            doc_relation=Footnote.DIGITAL_EDITION, source=footnote.source
        ).first()

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
            if diged_footnote:
                return diged_footnote

            # otherwise, make a new one
            new_footnote = Footnote(
                doc_relation=Footnote.DIGITAL_EDITION, source=footnote.source
            )
            # trying to set from related object footnote.document errors
            new_footnote.content_object = document
            new_footnote.save()
            # log footnote creation and return
            self.log_addition(
                new_footnote,
                "Created new footnote for migrated digital edition",
            )
            return new_footnote

        # when there is no additional information on the footnote
        else:
            # if a digital edition already exists, remove this one
            if diged_footnote:
                footnote.delete()
                # log deletion and and return existing diged
                self.log_deletion(footnote, "Removing redundant edition footnote")
                return diged_footnote

            # otherwise, convert edition to digital edition
            footnote.doc_relation = Footnote.DIGITAL_EDITION
            footnote.content = None
            footnote.save()
            # log footnote change and return
            self.log_change(footnote, "Migrated footnote to digital edition")
            return footnote

    # lookup to map tei git repo usernames to pgp db username for co-author string
    teicontributor_to_username = {
        "Alan Elbaum": "ae5677",
        # multiple Bens should all map to same user
        "Ben": "benj",
        "Ben Johnston": "benj",
        "benj@princeton.edu": "benj",
        "benjohnsto": "benj",
        # no github account that I can find; just use the name
        "Brendan Goldman": "Brendan Goldman",
        "Jessica Parker": "jp0630",
        "Ksenia Ryzhova": "kryzhova",
        "Rachel Richman": "rrichman",
        "mrustow": "mrustow",
        # multiple RSKs also...
        "Rebecca Sutton Koeser": "rkoeser",
        "rlskoeser": "rkoeser",
    }

    @cached_property
    def tei_contrib_users(self):
        # retrieve users from database based on known tei contributor usernames,
        # and return as a dict for lookup by username
        tei_users = User.objects.filter(
            username__in=set(self.teicontributor_to_username.values())
        )
        return {u.username: u for u in tei_users}

    def export_transcription(self, document, xmlfile):
        # get contributors and export to git backup

        # get the unique list of all contributors to this file
        commits = list(self.tei_gitrepo.iter_commits("master", paths=xmlfile))
        contributors = set([c.author.name for c in commits])
        # convert bitbucket users to unique set of pgp users
        contrib_usernames = set(
            self.teicontributor_to_username[c] for c in contributors
        )
        # now get actual users for those usernames...
        contrib_users = [self.tei_contrib_users.get(u, u) for u in contrib_usernames]

        # export transcription for the specified document,
        # documenting the users who modified the TEI file
        self.anno_exporter.export(
            pgpids=[document.pk],
            modifying_users=contrib_users,
            commit_msg="Transcription migrated from TEI %s" % xmlfile,
        )

    def log_addition(self, obj, log_message):
        "create a log entry documenting object creation"
        return self.log_entry(obj, log_message, ADDITION)

    def log_change(self, obj, log_message):
        "create a log entry documenting object change"
        return self.log_entry(obj, log_message, CHANGE)

    def log_deletion(self, obj, log_message):
        "create a log entry documenting object change"
        return self.log_entry(obj, log_message, DELETION)

    def check_unmigrated_footnotes(self):
        unmigrated_footnotes = Footnote.objects.filter(
            doc_relation__contains=Footnote.EDITION, content__isnull=False
        )
        if unmigrated_footnotes.exists():
            self.stdout.write(
                "\n%d unmigrated footnote%s"
                % (unmigrated_footnotes.count(), pluralize(unmigrated_footnotes))
            )
            for fn in unmigrated_footnotes:
                # provide admin link to make it easier to investigate
                admin_url = absolutize_url(
                    reverse("admin:footnotes_footnote_change", args=(fn.id,))
                )
                print("\t%s\t%s" % (fn, admin_url))

    _content_types = {}

    def get_content_type(self, obj):
        # lookup and cache content type for model
        model_class = obj.__class__
        if model_class not in self._content_types:
            self._content_types[model_class] = ContentType.objects.get_for_model(
                model_class
            )
        return self._content_types[model_class]

    def log_entry(self, obj, log_message, log_action):
        "create a log entry documenting object creation/change/deletion"
        # for this migration, we can assume user is always script user
        content_type = self.get_content_type(obj)
        return LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=content_type.pk,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message=log_message,
            action_flag=log_action,
        )


def new_transcription_annotation():
    # initialize a new annotation dict object with all the defaults set

    anno = Dict()
    setattr(anno, "@context", "http://www.w3.org/ns/anno.jsonld")
    anno.type = "Annotation"
    anno.body = [Dict()]
    anno.body[0].type = "TextualBody"
    # purpose on body is only needed if more than one body
    # (e.g., transcription + tags in the same annotation)
    # anno.body[0].purpose = "transcribing"
    anno.body[0].format = "text/html"
    # explicitly indicate text direction; all transcriptions are RTL
    anno.body[0].TextInput = "rtl"
    # supplement rather than painting over the image
    # multiple motivations are allowed; add transcribing as secondary motivation
    # (could use edm:transcribing from Europeana Data Model, but not sure
    # how to declare edm namespace)
    anno.motivation = ["sc:supplementing", "transcribing"]

    anno.target.source.type = "Canvas"
    anno.target.selector.type = "FragmentSelector"
    anno.target.selector.conformsTo = "http://www.w3.org/TR/media-frags/"

    return anno
