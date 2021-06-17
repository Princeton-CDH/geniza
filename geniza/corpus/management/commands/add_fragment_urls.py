import csv
import re
from collections import Counter

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from parasolr.django.signals import IndexableSignalHandler

from geniza.corpus.models import Fragment


class Command(BaseCommand):
    """Takes a CSV of shelfmarks and view URLs and/or IIIF URLs, update
    corresponding Fragment records in the database with those URLs.
    Expects CSV headers 'shelfmark' and one or both of 'url' and 'iiif_url'"""

    help = __doc__

    def __init__(self, *args, **options):
        super().__init__(*args, **options)

        self.stats = Counter()

        self.fragment_contenttype = ContentType.objects.get_for_model(Fragment)
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)
        parser.add_argument("-o", "--overwrite", action="store_true")
        parser.add_argument("-d", "--dryrun", action="store_true")

    def handle(self, *args, **options):
        self.csv_path = options.get("csv")
        self.overwrite = options.get("overwrite")
        self.dryrun = options.get("dryrun")

        try:
            with open(self.csv_path) as f:
                csvreader = csv.DictReader(f)
                for row in csvreader:
                    if "shelfmark" not in row or not (
                        "url" in row or "iiif_url" in row
                    ):
                        raise CommandError(
                            "CSV must include 'shelfmark' and one or both of 'url' and 'iiif_url'"
                        )
                    self.add_fragment_urls(row)
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {self.csv_path}")

        self.stdout.write(f"URLs added: {self.stats['url_added']}")
        self.stdout.write(f"URLs updated: {self.stats['url_updated']}")
        self.stdout.write(f"IIIF URLs added: {self.stats['iiif_added']}")
        self.stdout.write(f"IIIF URLs updated: {self.stats['iiif_updated']}")
        self.stdout.write(f"Fragments not found: {self.stats['not_found']}")
        self.stdout.write(f"Fragments skipped: {self.stats['skipped']}")

    def view_to_iiif_url(self, url):
        """Generate IIIF Manifest URL based on view url, if it can
        be determined automatically"""

        # cambridge iiif manifest links use the same id as view links
        # NOTE: should exclude search link like this one:
        # https://cudl.lib.cam.ac.uk/search?fileID=&keyword=T-s%2013J33.12&page=1&x=0&y=
        if "cudl.lib.cam.ac.uk/view/" in url:
            iiif_link = url.replace("/view/", "/iiif/")
            # view links end with /1 or /2 but iiif link does not include it
            iiif_link = re.sub(r"/\d$", "", iiif_link)
            return iiif_link

        return ""

    def add_fragment_urls(self, row):
        try:
            fragment = Fragment.objects.get(shelfmark=row["shelfmark"])
        except Fragment.DoesNotExist:
            self.stats["not_found"] += 1
            return

        url = row.get("url")
        iiif_url = row.get("iiif_url") or self.view_to_iiif_url(row["url"])
        save_needed = False
        log_message = []

        # if there is a view url, add or optionally update it
        if url:
            if not fragment.url:
                fragment.url = url
                self.stats["url_added"] += 1
                save_needed = True
                log_message.append("added URL")
            elif fragment.url != url:
                self.stdout.write(
                    "Fragment %s url differs: %s %s" % (fragment, fragment.url, url)
                )
                if self.overwrite:
                    fragment.url = url
                    self.stats["url_updated"] += 1
                    save_needed = True
                    log_message.append("updated URL")

        # similar logic for iiif url
        if iiif_url:
            if not fragment.iiif_url:
                fragment.iiif_url = iiif_url
                self.stats["iiif_added"] += 1
                save_needed = True
                log_message.append("added IIIF URL")
            elif fragment.iiif_url != iiif_url:
                self.stdout.write(
                    "Fragment %s IIIF url differs: %s %s"
                    % (fragment, fragment.iiif_url, iiif_url)
                )
                if self.overwrite:
                    self.stats["iiif_updated"] += 1
                    fragment.iiif_url = iiif_url
                    save_needed = True
                    log_message.append("updated IIIF URL")

        if save_needed:
            if self.dryrun:
                self.stdout.write(f"Set {fragment} url to {url} and iiif to {iiif_url}")
            else:
                fragment.save()
                self.log_change(fragment, " and ".join(log_message))
        else:
            self.stats["skipped"] += 1

    def log_change(self, fragment, message):
        # create log entry so there is a record of adding/updating urls
        LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=self.fragment_contenttype.pk,
            object_id=fragment.pk,
            object_repr=str(fragment),
            change_message=message,
            action_flag=CHANGE,
        )
