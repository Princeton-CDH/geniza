"""
Importing IIIF manifests to be cached in the database.

"""

import urllib

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from djiffy.importer import ManifestImporter
from djiffy.models import Manifest

from geniza.corpus.iiif_utils import GenizaManifestImporter
from geniza.corpus.models import Fragment


class Command(BaseCommand):
    """Import IIIF manifests into the local database."""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            nargs="*",
            help="One or more IIIF Collections or Manifests as file or URL (optional)",
        )
        parser.add_argument(
            "--update", action="store_true", help="Update previously imported manifests"
        )
        parser.add_argument(
            "--filter",
            help="Limit database manifests to update by url substring (optional)",
        )
        parser.add_argument(
            "--associate",
            action="store_true",
            help="Only associate fragments with imported manifests (no import)",
        )

    def handle(self, *args, **kwargs):
        # if fragment-manifest association is requested, run it and bail out
        if kwargs.get("associate"):
            self.associate_manifests()
            return

        # use command-line urls if specified
        iiif_urls = kwargs.get("path")
        # otherwise, import all iiif manifests referenced by fragments in the db
        if not iiif_urls:
            iiif_fragments = Fragment.objects.exclude(iiif_url="")
            # if a filter was specified, limit the objects to those that match
            if kwargs.get("filter"):
                iiif_fragments = iiif_fragments.filter(
                    iiif_url__contains=kwargs.get("filter")
                )
            iiif_urls = set(iiif_fragments.values_list("iiif_url", flat=True))
            # if we're not updating, filter out the ones we already have
            if not kwargs["update"]:
                already_imported = set(Manifest.objects.values_list("uri", flat=True))
                self.stdout.write(
                    "Skipping %d previously imported IIIF manifests"
                    % len(already_imported)
                )
                iiif_urls = iiif_urls - already_imported

            self.stdout.write(
                "%d IIIF urls associated with fragments to import" % len(iiif_urls)
            )

        importer = GenizaManifestImporter(
            stdout=self.stdout,
            stderr=self.stderr,
            style=self.style,
            update=kwargs["update"],
        )
        relinked = 0
        # import one url at a time so we know which manifest each url resolved to
        for iiif_url in iiif_urls:
            imported = importer.import_paths([iiif_url])
            if len(imported) == 1:
                relinked += self.relink_fragments(iiif_url, imported[0])
        if relinked:
            self.stdout.write("Relinked %d fragments to updated manifests" % relinked)

        self.associate_manifests()

    def relink_fragments(self, iiif_url, manifest):
        """Link fragments with the specified iiif url to the imported manifest.
        Manifest ids may not match the url they were loaded from (e.g., when
        a provider moves manifests to a new server and the old url returns
        the new manifest), in which case fragments would otherwise remain
        linked to a previously cached, outdated manifest."""
        fragments = Fragment.objects.filter(iiif_url=iiif_url).exclude(
            manifest=manifest
        )
        updated = 0
        for fragment in fragments:
            fragment.manifest = manifest
            fragment.save()
            updated += 1
        return updated

    def associate_manifests(self):
        """update fragments with iiif urls to add foreign keys to the new manifests"""
        fragments = Fragment.objects.exclude(iiif_url="").filter(manifest__isnull=True)
        self.stdout.write(
            "%d fragments with iiif url but unlinked manifest" % fragments.count()
        )
        updated = 0
        for fragment in fragments:
            # a set of ~200 manifest urls were entered with double slashes,
            # resulting in a mismatch with the imported manifest objects.
            # parse the url and clean up if present
            parsed = urllib.parse.urlparse(fragment.iiif_url)
            if parsed.path.startswith("//"):
                # remove the extra slash and then reassemble the url
                url_path = parsed.path[1:]
                fragment.iiif_url = urllib.parse.urlunparse(
                    (parsed.scheme, parsed.netloc, url_path, "", "", "")
                )

            fragment.manifest = Manifest.objects.filter(uri=fragment.iiif_url).first()
            if fragment.manifest:
                fragment.save()
                updated += 1

        self.stdout.write("Updated %d fragments with link to manifest" % updated)
