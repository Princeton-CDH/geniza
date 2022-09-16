import json
import os
from collections import defaultdict
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from django.template.loader import get_template
from django.utils.text import slugify
from git import InvalidGitRepositoryError, Repo

from geniza.annotations.models import Annotation, annotations_to_list
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote


class Command(BaseCommand):
    """Backup annotation data and synchronize to GitHub"""

    v_normal = 1  # default verbosity

    def add_arguments(self, parser):
        parser.add_argument(
            "pgpids", nargs="*", help="Export the specified documents only"
        )

    def handle(self, *args, **options):
        self.verbosity = options["verbosity"]
        if not getattr(settings, "ANNOTATION_BACKUP_PATH"):
            raise CommandError(
                "Please configure ANNOTATION_BACKUP_PATH in django settings"
            )
        base_output_dir = settings.ANNOTATION_BACKUP_PATH
        # initialize git repo interface for output path
        try:
            repo = self.setup_repo(
                base_output_dir, getattr(settings, "ANNOTATION_BACKUP_GITREPO", None)
            )
        except InvalidGitRepositoryError:
            print("%s is not a valid git repository" % base_output_dir)
            return

        annotations_output_dir = os.path.join(base_output_dir, "annotations")

        # define paths and ensure directories exist for compiled transcription
        transcription_output_dir = {}
        for output_format in ["txt", "html"]:
            format_path = os.path.join(base_output_dir, "transcriptions", output_format)
            transcription_output_dir[output_format] = format_path
            os.makedirs(format_path, exist_ok=True)

        # identify content to backup based on documents with digital editions

        docs = Document.objects.filter(
            footnotes__doc_relation__contains=Footnote.DIGITAL_EDITION
        ).distinct()
        # if ids are specified, limit to just those documents
        if options["pgpids"]:
            docs = docs.filter(pk__in=options["pgpids"])

        self.stdout.write(
            "Backing up annotations for %d document%s with digital editions"
            % (docs.count(), pluralize(docs))
        )

        # filenames to be committed to git repo
        updated_filenames = []

        for document in docs:
            print(document)
            # use PGPID for annotation directory name
            # path based on recommended uri pattern from the spec
            # {prefix}/{identifier}/list/{name}
            output_dir = os.path.join(annotations_output_dir, str(document.id), "list")
            # ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # find all annotations for this document
            # sort by schema:position if available
            annos = Annotation.objects.filter(
                content__target__source__partOf__id=document.manifest_uri
            ).order_by("content__schema:position", "created")

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
                updated_filenames.append(annolist_out_path)
                with open(annolist_out_path, "w") as outfile:
                    json.dump(
                        annotations_to_list(annotations, uri="test"), outfile, indent=2
                    )

            # load django template for rendering html export
            html_template = get_template("corpus/transcription_export.html")

            # for convenience and more readable versioning, also generate
            # text and html transcription files
            for edition in document.digital_editions():
                # print(edition, edition.source)
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

        # prep updated files for commit to git repo
        #  - adjust paths so they are relative to git root
        updated_filenames = [
            f.replace(base_output_dir, "").lstrip("/") for f in updated_filenames
        ]
        repo.index.add(updated_filenames)
        if repo.is_dirty():
            print("Committing changes")
            repo.index.commit("Automated data export from PGP")
            try:
                origin = repo.remote(name="origin")
                # pull any remote changes
                origin.pull()
                # push data updates
                result = origin.push()
                # output push summary in case anything bad happens
                for pushinfo in result:
                    print(pushinfo.summary)
            except ValueError:
                print("No origin repository, unable to push updates")
        else:
            print("No changes")

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
            path = parsed_url.path.split("/")[-1]
        else:
            # otherwise use the portion of the path after any iiif prefix
            # or full path if it does not include /iiif/
            path = parsed_url.path.partition("/iiif/")[2] or parsed_url.path
            # remove trailing any slash and replace the rest with _
            # (using underscore because cudl manifest ids use dashes)
            path = path.rstrip("/").replace("/", "_")

        return "_".join([prefix, path])

    def transcription_filename(self, document, source):
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

    def setup_repo(self, local_path, remote_git_url=None):
        """ensure git repository has been cloned and content is up to date"""

        if remote_git_url is None:
            # should only really be ok for development
            self.stdout.write(self.style.WARNING("Remote git url is not configured"))

        # if directory does not yet exist, clone repository
        if not os.path.isdir(local_path):
            if self.verbosity >= self.v_normal:
                self.stdout.write("Cloning annotations export repository")
            # clone remote to configured path
            Repo.clone_from(url=remote_git_url, to_path=local_path)
            # then initialize the repo object
            repo = Repo(local_path)
        else:
            # pull any changes since the last run
            repo = Repo(local_path)
            if remote_git_url:
                repo.remotes.origin.pull()

        return repo
