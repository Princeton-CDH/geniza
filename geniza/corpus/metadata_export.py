import csv
import os

from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.sites.models import Site
from django.db.models.query import Prefetch
from django.http import StreamingHttpResponse
from django.utils import timezone
from rich.progress import track

script_user = settings.SCRIPT_USERNAME
site_domain = Site.objects.get_current().domain.rstrip("/")
url_scheme = "https://"

from geniza.common.utils import Echo, timeprint
from geniza.corpus.models import Document, TextBlock


class Exporter:
    model = None
    csv_fields = []
    sep_within_cells = "; "
    progress = True

    def __init__(self, queryset=None):
        self.queryset = queryset

    def csv_filename(self):
        str_plural = self.model._meta.verbose_name_plural
        str_time = timezone.now().strftime("%Y%m%dT%H%M%S")
        return f"geniza-{str_plural}-{str_time}.csv"

    def get_queryset(self):
        return (
            self.model.objects.metadata_prefetch()
            if not self.queryset
            else self.queryset
        )

    def get_export_data_dict(self, obj):
        # THIS NEEDS TO BE SUBCLASSED
        raise NotImplementedError

    def iter_export_data_as_dicts(self, progress=None):
        timeprint("iter_export_data_as_dicts")
        # get queryset
        queryset = self.get_queryset()

        # progress bar?
        iterr = (
            queryset
            if not (self.progress if progress is None else progress)
            else track(queryset, description=f"Writing rows to file")
        )

        # save
        yield from (self.get_export_data_dict(obj) for obj in iterr)

    def iter_export_data_as_csv(self, fn=None, pseudo_buffer=False, progress=None):
        timeprint("iter_export_data_as_csv")
        with (
            open(self.csv_filename() if not fn else fn, "w")
            if not pseudo_buffer
            else Echo()
        ) as of:
            writer = csv.DictWriter(
                of, fieldnames=self.csv_fields, extrasaction="ignore"
            )
            yield writer.writeheader()
            yield from (
                writer.writerow(docd)
                for docd in self.iter_export_data_as_dicts(progress=progress)
            )

    def write_export_data_csv(self, fn=None, progress=True):
        timeprint("write_export_data_csv")
        if not fn:
            fn = self.csv_filename()
        for row in self.iter_export_data_as_csv(
            fn=fn, pseudo_buffer=False, progress=progress
        ):
            pass

    def http_export_data_csv(self, fn=None, progress=False):
        timeprint("http_export_data_csv")
        if not fn:
            fn = self.csv_filename()
        iterr = self.iter_export_data_as_csv(pseudo_buffer=True, progress=progress)
        response = StreamingHttpResponse(iterr, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f"attachment; filename={fn}"
        return response


class DocumentExporter(Exporter):
    model = Document
    csv_fields = [
        "pgpid",
        "url",
        "iiif_urls",
        "fragment_urls",
        "shelfmark",
        "multifragment",
        "side",
        "region",
        "type",
        "tags",
        "description",
        "shelfmarks_historic",
        "languages_primary",
        "languages_secondary",
        "language_note",
        "doc_date_original",
        "doc_date_calendar",
        "doc_date_standard",
        "notes",
        "needs_review",
        "url_admin",
        "initial_entry",
        "last_modified",
        "input_by",
        "status",
        "library",
        "collection",
    ]

    def get_export_data_dict(self, doc):
        all_textblocks = doc.textblock_set.all()
        all_fragments = [tb.fragment for tb in all_textblocks]
        all_log_entries = doc.log_entries.all()
        input_users = set(
            [
                log_entry.user
                for log_entry in all_log_entries
                if log_entry.user.username != script_user
            ]
        )
        iiif_urls = [fr.iiif_url for fr in all_fragments]
        view_urls = [fr.url for fr in all_fragments]
        multifrag = [tb.multifragment for tb in all_textblocks]
        side = [tb.side for tb in all_textblocks]
        region = [tb.region for tb in all_textblocks]
        old_shelfmarks = [fragment.old_shelfmarks for fragment in all_fragments]
        libraries = set(
            [
                fragment.collection.lib_abbrev or fragment.collection.library
                if fragment.collection
                else ""
                for fragment in all_fragments
            ]
        ) - {
            ""
        }  # exclude empty string for any fragments with no library
        collections = set(
            [
                fragment.collection.abbrev or fragment.collection.name
                if fragment.collection
                else ""
                for fragment in all_fragments
            ]
        ) - {
            ""
        }  # exclude empty string for any with no collection

        outd = {}
        outd["pgpid"] = doc.id

        # to make the download as efficient as possible, don't use
        # absolutize_url, reverse, or get_absolute_url methods
        outd[
            "url"
        ] = f"{url_scheme}{site_domain}/documents/{doc.id}/"  # public site url

        sep_within_cells = self.sep_within_cells

        outd["iiif_urls"] = sep_within_cells.join(iiif_urls) if any(iiif_urls) else ""
        outd["fragment_urls"] = (
            sep_within_cells.join(view_urls) if any(view_urls) else ""
        )
        outd["shelfmark"] = doc.shelfmark
        outd["multifragment"] = sep_within_cells.join([s for s in multifrag if s])
        outd["side"] = sep_within_cells.join(
            [s for s in side if s]
        )  # side (recto/verso)
        outd["region"] = sep_within_cells.join(
            [r for r in region if r]
        )  # text block region
        outd["type"] = doc.doctype
        outd["tags"] = doc.all_tags()
        outd["description"] = doc.description
        outd["shelfmarks_historic"] = sep_within_cells.join(
            [os for os in old_shelfmarks if os]
        )
        outd["languages_primary"] = doc.all_languages()
        outd["languages_secondary"] = doc.all_secondary_languages()
        outd["language_note"] = doc.language_note
        outd["doc_date_original"] = doc.doc_date_original
        outd["doc_date_calendar"] = doc.doc_date_calendar
        outd["doc_date_standard"] = doc.doc_date_standard
        outd["notes"] = doc.notes
        outd["needs_review"] = doc.needs_review
        outd[
            "url_admin"
        ] = f"{url_scheme}{site_domain}/admin/corpus/document/{doc.id}/change/"

        # default sort is most recent first, so initial input is last
        outd["initial_entry"] = (
            all_log_entries.last().action_time if all_log_entries else ""
        )

        outd["last_modified"] = doc.last_modified

        outd["input_by"] = sep_within_cells.join(
            set([user.get_full_name() or user.username for user in input_users])
        )

        outd["status"] = doc.get_status_display()
        outd["library"] = sep_within_cells.join(libraries) if any(libraries) else ""
        outd["collection"] = (
            sep_within_cells.join(collections) if any(collections) else ""
        )

        return outd
