CSV_EXPORT_PROGRESS = True
SEP_WITHIN_CELLS = "; "
CSV_FIELDS = [
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


## adapted from tabular_export.admin
class Echo(object):
    # See https://docs.djangoproject.com/en/1.8/howto/outputting-csv/#streaming-csv-files
    def write(self, value):
        return value

    def __enter__(self, *x, **y):
        return self

    def __exit__(self, *x, **y):
        return


import csv
import os

from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.sites.models import Site
from django.db.models.query import Prefetch
from django.http import StreamingHttpResponse
from tabular_export.admin import export_to_csv_response

# from rich.progress import track
from tqdm import tqdm as track

script_user = settings.SCRIPT_USERNAME
site_domain = Site.objects.get_current().domain.rstrip("/")
url_scheme = "https://"

from geniza.common.utils import timeprint
from geniza.corpus.models import Document, TextBlock

## @TODO subclass QuerySet


def get_docs_to_export():
    timeprint("Querying")
    docs = Document.metadata_objects.all()
    # docs = (
    #     Document.objects.all()
    #     .select_related("doctype")
    #     .prefetch_related(
    #         "tags",
    #         "languages",
    #         Prefetch(
    #             "textblock_set",
    #             queryset=TextBlock.objects.select_related(
    #                 "fragment", "fragment__collection"
    #             ),
    #         ),
    #     )
    #     .annotate(shelfmk_all=ArrayAgg("textblock__fragment__shelfmark"))
    #     .order_by("shelfmk_all")
    # )
    timeprint("Done querying")
    return docs


def get_export_data_for_doc(doc, sep_within_cells=SEP_WITHIN_CELLS):
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
    outd["url"] = f"{url_scheme}{site_domain}/documents/{doc.id}/"  # public site url
    outd["iiif_urls"] = sep_within_cells.join(iiif_urls) if any(iiif_urls) else ""
    outd["fragment_urls"] = sep_within_cells.join(view_urls) if any(view_urls) else ""
    outd["shelfmark"] = doc.shelfmark
    outd["multifragment"] = sep_within_cells.join([s for s in multifrag if s])
    outd["side"] = sep_within_cells.join([s for s in side if s])  # side (recto/verso)
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
    outd["initial_entry"] = (
        all_log_entries.last().action_time if all_log_entries else ""
    )
    outd["last_modified"] = doc.last_modified
    outd["input_by"] = sep_within_cells.join(
        sorted(
            list(set([user.get_full_name() or user.username for user in input_users]))
        )
    )  # sorting to ensure deterministic order
    outd["status"] = doc.get_status_display()
    outd["library"] = sep_within_cells.join(libraries) if any(libraries) else ""
    outd["collection"] = sep_within_cells.join(collections) if any(collections) else ""

    return outd


def iter_export_data_for_docs(
    docs=None,
    progress=CSV_EXPORT_PROGRESS,
    sep_within_cells=SEP_WITHIN_CELLS,
):
    timeprint("iter_export_data_for_docs()")

    # get docs
    if not docs:
        docs = get_docs_to_export()

    # progress bar?
    timeprint("Beginning to write")
    iterr = docs if not progress else track(docs, desc=f"Writing rows to file")

    # save
    for doc in iterr:
        yield get_export_data_for_doc(doc, sep_within_cells=sep_within_cells)


def iter_export_data_for_docs_as_ll(
    docs=None, csv_fields=CSV_FIELDS, progress=CSV_EXPORT_PROGRESS, default="", **kwargs
):
    timeprint("iter_export_data_for_docs_as_ll()")
    iterr = iter_export_data_for_docs(docs=docs, progress=progress, **kwargs)
    for docd in iterr:
        yield [docd.get(h, default) for h in csv_fields]


def stream_export_data_for_docs(
    fn="pgp_documents.csv",
    docs=None,
    pseudo_buffer=False,
    csv_fields=CSV_FIELDS,
    **kwargs,
):
    timeprint("stream_export_data_for_docs()")
    with (open(fn, "w") if not pseudo_buffer else Echo()) as of:
        writer = csv.DictWriter(of, fieldnames=csv_fields, extrasaction="ignore")
        yield writer.writeheader()
        for docd in iter_export_data_for_docs(docs=docs):
            yield writer.writerow(docd)


def write_stream_export_data_for_docs(
    fn="pgp_documents.csv", docs=None, csv_fields=CSV_FIELDS, **kwargs
):
    timeprint("write_stream_export_data_for_docs()")
    for row in stream_export_data_for_docs(
        fn=fn, docs=docs, csv_fields=csv_fields, **kwargs
    ):
        pass


def http_stream_export_data_for_docs(
    fn="pgp_documents_download.csv", docs=None, csv_fields=CSV_FIELDS
):
    """Returns a downloadable StreamingHttpResponse using an CSV payload generated from headers and rows"""
    timeprint("http_stream_export_data_for_docs()")
    iterr = stream_export_data_for_docs(
        fn=fn, docs=docs, csv_fields=csv_fields, pseudo_buffer=True
    )
    response = StreamingHttpResponse(iterr, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename={fn}"
    return response
