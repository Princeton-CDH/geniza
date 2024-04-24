import glob
import json
import logging
import math
import os
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.template.defaultfilters import pluralize
from django.template.loader import get_template
from django.urls import reverse
from django.utils.text import slugify
from git import GitCommandError, Repo

from geniza.annotations.models import Annotation, annotations_to_list
from geniza.common.utils import absolutize_url
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote

logger = logging.getLogger(__name__)


def generate_coauthor_commit(modifying_users):
    """Given a list of users, generate a GitHub co-author commit message."""

    # construct co-author commit and add to the commit message
    coauthors = []
    # first name, last name, coauthor email
    coauth_msg = "Co-authored-by: %s <%s>"
    for user in modifying_users:
        # special case: there is one TEI bitbucket contributor
        # without a github account; handle user as bare string
        if isinstance(user, str):
            display_name = user
        else:
            # username as fallback in case last/first names not set
            display_name = user.get_full_name().strip() or user.username

        coauthor_email = None
        try:
            # if github coauthor is available, add to list of coauthors
            coauthor_email = user.profile.github_coauthor
        except (User.profile.RelatedObjectDoesNotExist, AttributeError):
            # ignore error if user has no profile,
            # or if given a string instead of a User
            pass

        # always list name or username as co-author, even if no email
        # GitHub won't be able to parse it, but it will be tracked)
        if coauthor_email:
            # co-author with email
            coauthors.append(coauth_msg % (display_name, coauthor_email))
        else:
            # co-author with name only
            coauthors.append("Co-authored-by: %s" % display_name)

    return "\n".join(coauthors)


class AnnotationExporter:
    v_normal = 1

    #: default commit message
    default_commit_msg = "Automated data export from PGP"

    def __init__(
        self,
        pgpids=None,
        stdout=None,
        push_changes=True,
        verbosity=None,
        modifying_users=None,
        commit_msg=None,
    ):
        # check that required settings are available
        if not getattr(settings, "ANNOTATION_BACKUP_PATH") or not getattr(
            settings, "ANNOTATION_BACKUP_GITREPO"
        ):
            raise Exception(
                "Settings for ANNOTATION_BACKUP_PATH and ANNOTATION_BACKUP_GITREPO are required"
            )

        self.base_output_dir = settings.ANNOTATION_BACKUP_PATH
        self.annotations_output_dir = os.path.join(self.base_output_dir, "annotations")
        self.git_repo = settings.ANNOTATION_BACKUP_GITREPO
        self.pgpids = pgpids
        self.push_changes = push_changes
        self.verbosity = verbosity if verbosity is not None else self.v_normal
        self.stdout = stdout
        self.modifying_users = modifying_users
        # allow overriding default commit message
        self.commit_msg = commit_msg or self.default_commit_msg

    def export(self, pgpids=None, modifying_users=None, commit_msg=None):
        # allow overriding pgpid, modifying users, or commit message for this export
        if pgpids:
            self.pgpids = pgpids
        if modifying_users:
            self.modifying_users = modifying_users
        if commit_msg:
            self.commit_msg = commit_msg

        # initialize git repo interface for configured output path & repo
        self.setup_repo()

        # define paths and ensure directories exist for compiled transcription

        # identify content to export

        # if ids are specified, limit to just those documents
        if self.pgpids:
            # NOTE: must not filter by digital edition, since we need
            # to support cleaning up old files on transcription delete
            docs = Document.objects.filter(pk__in=self.pgpids)

        # otherwise, get all documents with digital editions/translations
        else:
            docs = Document.objects.filter(
                Q(footnotes__doc_relation__contains=Footnote.DIGITAL_EDITION)
                | Q(footnotes__doc_relation__contains=Footnote.DIGITAL_TRANSLATION)
            ).distinct()

        self.output_info(
            "Backing up annotations for %d document%s with digital edition or translation"
            % (docs.count(), pluralize(docs)),
        )

        # keep track of exported files to be committed to git
        updated_filenames = []
        # and files that should be removed
        remove_filenames = []

        # load django template for rendering html export
        html_template = {
            "transcription": get_template("corpus/transcription_export.html"),
            "translation": get_template("corpus/translation_export.html"),
        }
        # search uri will be the basis for our annotation list uris
        anno_search_uri = absolutize_url(reverse("annotations:search"))

        for document in docs:
            self.output_info(str(document))
            # use PGPID for annotation directory name
            # path based on recommended uri pattern from the spec
            # {prefix}/{identifier}/list/{name}
            doc_output_dir = self.document_path(document.pk)
            doc_annotations_dir = os.path.join(
                self.annotations_output_dir, doc_output_dir, "list"
            )
            doc_transcription_dir = os.path.join(self.base_output_dir, doc_output_dir)
            # ensure output directories exist
            os.makedirs(doc_annotations_dir, exist_ok=True)
            os.makedirs(doc_transcription_dir, exist_ok=True)

            # get a list of existing files so we can cleanup removed content
            # - annotation lists
            doc_existing_files = glob.glob(os.path.join(doc_annotations_dir, "*.json"))
            doc_existing_files.extend(
                glob.glob(
                    os.path.join(doc_transcription_dir, "PGPID%s_*" % document.pk)
                )
            )

            # track updated files for this document so we can check
            # for any existing files that should be removed
            doc_updated_files = []

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
                    doc_annotations_dir, "%s.json" % annolist_name
                )
                doc_updated_files.append(annolist_out_path)

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
            for footnote in document.digital_footnotes():
                self.debug("%s %s" % (footnote, footnote.source))
                # filename based on pgpid and source authors;
                # explicitly label as transcription/translation for context
                fn_type = (
                    "transcription"
                    if Footnote.DIGITAL_EDITION in footnote.doc_relation
                    else "translation"
                )
                base_filename = AnnotationExporter.filename(
                    document, footnote.source, fn_type
                )
                for output_format in ["txt", "html"]:
                    # put in the directory for this document;
                    # use format as file extension
                    outfile_path = os.path.join(
                        doc_transcription_dir,
                        "%s.%s" % (base_filename, output_format),
                    )
                    with open(outfile_path, "w") as outfile:
                        if output_format == "html":
                            content = html_template[fn_type].render(
                                {"document": document, "edition": footnote}
                            )
                        else:
                            # text version is meant for corpus analytics,
                            # so should be minimal and content only
                            content = footnote.content_text
                        if content:
                            # don't write/add to updated if no content
                            outfile.write(content)
                            doc_updated_files.append(outfile_path)

            # add all updated files for this document to the updated list
            updated_filenames.extend(doc_updated_files)
            # check if there are any files to be removed; add to remove list
            extra_doc_files = set(doc_existing_files) - set(doc_updated_files)
            remove_filenames.extend(extra_doc_files)

        # commit and push (if configured) all the exported files
        self.commit_changed_files(updated_filenames, remove_filenames)

        # return a count of the number of documents processed
        return len(docs)

    def cleanup(self, document_id, modifying_users=None, commit_msg=None):
        "Cleanup files when both annotation and document have been removed."
        self.output_info("Removing all exported files for PGPID %s" % document_id)
        # NOTE: some duplication here from main export method
        if modifying_users:
            self.modifying_users = modifying_users
        if commit_msg:
            self.commit_msg = commit_msg

        # use PGPID for annotation directory name
        # path based on recommended uri pattern from the spec
        # {prefix}/{identifier}/list/{name}
        doc_output_dir = self.document_path(document_id)
        doc_annotations_dir = os.path.join(
            self.annotations_output_dir, doc_output_dir, "list"
        )
        doc_transcription_dir = os.path.join(self.base_output_dir, doc_output_dir)

        # get a list of existing files to be  cleaned up
        existing_files = glob.glob(os.path.join(doc_annotations_dir, "*.json"))
        existing_files.extend(
            glob.glob(os.path.join(doc_transcription_dir, "PGPID%s_*" % document_id))
        )

        # commit changes removing all existing files
        self.commit_changed_files([], existing_files)

    def document_path(self, pgpid):
        """Generate path based on pgpid so records are chunked by 1000s,
        then nested by pgpid to avoid too many files in a single directory."""

        # round pgpid to nearest 1000; pad with leading zeros for
        # so all directories have 5 digits; use actual PGPID for subdirectory
        k_chunk = math.floor(int(pgpid) / 1000) * 1000
        return os.path.join(f"{k_chunk:05d}", str(pgpid))

    def commit_changed_files(self, updated_filenames, remove_filenames):
        # prep updated files for commit to git repo
        #  - adjust paths so they are relative to git root
        updated_filenames = [
            f.replace(self.base_output_dir, "").lstrip("/") for f in updated_filenames
        ]
        self.repo.index.add(updated_filenames)

        git_remove_filenames = [
            f.replace(self.base_output_dir, "").lstrip("/") for f in remove_filenames
        ]
        # remove obsolete files, if any
        if remove_filenames:
            # if file is not in git index, this will error
            try:
                self.repo.index.remove(git_remove_filenames)
            except GitCommandError:
                # ignore; file was not in git index, will be removed
                pass

            # remove from file system as well
            for old_file in remove_filenames:
                os.remove(old_file)

        if self.repo.is_dirty():
            self.repo.index.commit(self.get_commit_message())
            if self.push_changes:
                self.sync_github()
        # otherwise, no changes to push

    def get_commit_message(self):
        # construct co-author commit (if any) and add to the commit message
        if not self.modifying_users:
            return self.commit_msg
        return "%s\n\n%s" % (
            self.commit_msg,
            generate_coauthor_commit(self.modifying_users),
        )

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
    def filename(document, source, fn_type):
        # filename based on pgpid and source authors;
        # explicitly label as transcription/translation for context
        authors = [a.creator.last_name for a in source.authorship_set.all()] or [
            "machine-generated"
            if "model" in source.source_type.type
            else "unknown author"
        ]

        return "PGPID%(pgpid)s_s%(source_id)d_%(authors)s_%(text_type)s" % {
            "pgpid": document.id,
            "source_id": source.id,
            "authors": slugify(" ".join(authors)),
            "text_type": fn_type,
        }

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
