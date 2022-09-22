import json
import logging
import os
from collections import defaultdict
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from django.template.loader import get_template
from django.urls import reverse
from django.utils.text import slugify
from git import InvalidGitRepositoryError, Repo

from geniza.annotations.models import Annotation, annotations_to_list
from geniza.common.utils import absolutize_url
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote

logger = logging.getLogger(__name__)


class AnnotationExporter:
    v_normal = 1

    def __init__(self, pgpids=None, stdout=None, push_changes=True, verbosity=None):
        # check that required settings are available
        if not getattr(settings, "ANNOTATION_BACKUP_PATH") or not getattr(
            settings, "ANNOTATION_BACKUP_GITREPO"
        ):
            raise Exception(
                "Settings for ANNOTATION_BACKUP_PATH and ANNOTATION_BACKUP_GITREPO are required"
            )

        self.base_output_dir = settings.ANNOTATION_BACKUP_PATH
        self.git_repo = settings.ANNOTATION_BACKUP_GITREPO
        self.pgpids = pgpids
        self.push_changes = push_changes
        self.verbosity = verbosity if verbosity is not None else self.v_normal
        self.stdout = stdout

    def export(self):

        # initialize git repo interface for configured output path & repo
        self.setup_repo()

        # define paths and ensure directories exist for compiled transcription
        annotations_output_dir = os.path.join(self.base_output_dir, "annotations")

        transcription_output_dir = {}
        for output_format in ["txt", "html"]:
            format_path = os.path.join(
                self.base_output_dir, "transcriptions", output_format
            )
            transcription_output_dir[output_format] = format_path
            os.makedirs(format_path, exist_ok=True)

        # identify content to backup based on documents with digital editions
        docs = Document.objects.filter(
            footnotes__doc_relation__contains=Footnote.DIGITAL_EDITION
        ).distinct()
        # if ids are specified, limit to just those documents
        if self.pgpids:
            docs = docs.filter(pk__in=self.pgpids)
        self.output_info(
            "Backing up annotations for %d document%s with digital edition"
            % (docs.count(), pluralize(docs)),
        )

        # keep track of exported files to be committed to git
        updated_filenames = []

        # load django template for rendering html export
        html_template = get_template("corpus/transcription_export.html")
        # search uri will be the basis for our annotation list uris
        anno_search_uri = absolutize_url(reverse("annotations:search"))

        for document in docs:
            self.output_info(str(document))
            # use PGPID for annotation directory name
            # path based on recommended uri pattern from the spec
            # {prefix}/{identifier}/list/{name}
            doc_output_dir = os.path.join(
                annotations_output_dir, str(document.id), "list"
            )
            # ensure output directory exists
            os.makedirs(doc_output_dir, exist_ok=True)

            # find all annotations for this document
            # sort by schema:position if available
            # for annotation list backup, we don't need to segment
            # by motivation, source, etc; just group by canvas
            annos_by_canvas = (
                Annotation.objects.by_target_context(document.manifest_uri)
                .order_by("content__schema:position", "created")
                .group_by_canvas()
            )

            # create and save one AnnotationList per canvas
            # with all associated annotations, as a backup
            # that could be imported into any w3c annotation server
            for canvas, annotations in annos_by_canvas.items():
                annolist_name = AnnotationExporter.annotation_list_name(canvas)
                annolist_out_path = os.path.join(
                    doc_output_dir, "%s.json" % annolist_name
                )
                updated_filenames.append(annolist_out_path)

                # construct the url to search for this set of annotations
                # and use it as the uri for the saved annotation list
                search_args = {"uri": canvas, "manifest": document.manifest_uri}
                annolist_uri = "%s?%s" % (anno_search_uri, urlencode(search_args))
                with open(annolist_out_path, "w") as outfile:
                    json.dump(
                        # FIXME: correct this test uri
                        annotations_to_list(annotations, uri=annolist_uri),
                        outfile,
                        indent=2,
                    )

            # for convenience and more readable versioning, also generate
            # text and html transcription files
            for edition in document.digital_editions():
                self.debug("%s %s" % (edition, edition.source))
                # filename based on pgpid and source authors;
                # explicitly label as transcription for context
                base_filename = AnnotationExporter.transcription_filename(
                    document, edition.source
                )
                for output_format in ["txt", "html"]:
                    # put in the appropriate transription dir by format,
                    # use format as file extension
                    outfile_path = os.path.join(
                        transcription_output_dir[output_format],
                        "%s.%s" % (base_filename, output_format),
                    )
                    updated_filenames.append(outfile_path)
                    with open(outfile_path, "w") as outfile:
                        if output_format == "html":
                            content = html_template.render(
                                {"document": document, "edition": edition}
                            )
                            outfile.write(content)
                        else:
                            # text version is meant for corpus analytics,
                            # so should be minimal and content only
                            outfile.write(edition.content_text)

        # commit and push (if configured) all the exported files
        self.commit_changed_files(updated_filenames)

    def commit_changed_files(self, updated_filenames):
        # prep updated files for commit to git repo
        #  - adjust paths so they are relative to git root
        updated_filenames = [
            f.replace(self.base_output_dir, "").lstrip("/") for f in updated_filenames
        ]
        self.repo.index.add(updated_filenames)
        if self.repo.is_dirty():
            self.repo.index.commit("Automated data export from PGP")
            if self.push_changes:
                self.sync_github()
        # otherwise, no changes to push

    def sync_github(self):
        """Sync local repository content with origin repository. Assumes
        :meth:`setup_repo` has already been run, and any new or modified
        files have been committed."""
        try:
            origin = self.repo.remote(name="origin")
            # pull any remote changes since our last commit
            origin.pull()
            # push data updates
            result = origin.push()
            # NOTE: could add debug logging of push summary,
            # in case anything bad happens; usually only commit hashes
            # for pushinfo in result:
            #     print(pushinfo.summary)
        except ValueError:
            self.warn("No origin repository, unable to push updates")

    @staticmethod
    def annotation_list_name(canvas_uri):
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

        # remove any extension (e.g., for static manifests)
        path = os.path.splitext(parsed_url.path)[0]

        # figgy uses uuids; canvas id is last portion of path and is reliably unique
        if "figgy" in parsed_url.hostname:
            path = path.split("/")[-1]
        else:
            # otherwise use the portion of the path after any iiif prefix
            # or full path if it does not include /iiif/
            path = path.partition("/iiif/")[2] or parsed_url.path
            # remove trailing any slash and replace the rest with _
            # (using underscore because cudl manifest ids use dashes)
            path = path.rstrip("/").replace("/", "_")

        return "_".join([prefix, path])

    @staticmethod
    def transcription_filename(document, source):
        # filename based on pgpid and source authors;
        # explicitly label as transcription for context
        authors = [a.creator.last_name for a in source.authorship_set.all()] or [
            "unknown author"
        ]

        return "PGPID%s_s%d_%s_transcription" % (
            document.id,
            source.id,
            slugify(" ".join(authors)),
        )

    # map log level to django manage command verbosity
    log_level_to_verbosity = {
        logging.DEBUG: 2,
        logging.INFO: 1,  # = normal
        # considering anything else zero (important to see in quiet mode)
    }

    # handle either logging or manage command output
    def output_message(self, message, log_level):
        """output a message to logger or manage command stdout at the
        specified log level; honors verbosity setting for stdout."""
        if self.stdout:
            v_level = self.log_level_to_verbosity.get(log_level, 0)
            if self.verbosity >= v_level:
                self.stdout.write(message)
        else:
            logger.log(log_level, message)

    def output_info(self, message):
        "Output an info level message"
        self.output_message(message, logging.INFO)

    def warn(self, message):
        "Output a warning"
        self.output_message(message, logging.WARNING)

    def debug(self, message):
        "Output a debug level message"
        self.output_message(message, logging.DEBUG)

    def setup_repo(self):
        """ensure git repository has been cloned and content is up to date"""

        local_path = self.base_output_dir
        remote_git_url = self.git_repo

        # if directory does not yet exist, clone repository
        if not os.path.isdir(local_path):
            self.output_info("Cloning annotations export repository")

            # clone remote to configured path
            Repo.clone_from(url=remote_git_url, to_path=local_path)
            # then initialize the repo object
            self.repo = Repo(local_path)
        else:
            # pull any changes since the last run
            self.repo = Repo(local_path)
            # only pull / synchronize when we are pushing changes
            if self.push_changes:
                self.repo.remotes.origin.pull()
