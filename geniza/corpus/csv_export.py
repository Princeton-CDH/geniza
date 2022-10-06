import csv

from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.sites.models import Site
from django.db.models.query import Prefetch
from rich.progress import track

from geniza.corpus.models import Document, TextBlock


def get_docs_to_export():
    return (
        Document.objects.all()
        .select_related("doctype")
        .prefetch_related(
            "tags",
            "languages",
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment", "fragment__collection"
                ),
            ),
        )
        .annotate(shelfmk_all=ArrayAgg("textblock__fragment__shelfmark"))
        .order_by("shelfmk_all")
    )


def get_export_data_for_doc(doc):
    script_user = settings.SCRIPT_USERNAME
    site_domain = Site.objects.get_current().domain.rstrip("/")
    url_scheme = "https://"

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
    outd["iiif_urls"] = ";".join(iiif_urls) if any(iiif_urls) else ""
    outd["fragment_urls"] = ";".join(view_urls) if any(view_urls) else ""
    outd["shelfmark"] = doc.shelfmark
    outd["multifragment"] = ";".join([s for s in multifrag if s])
    outd["side"] = ";".join([s for s in side if s])  # side (recto/verso)
    outd["region"] = ";".join([r for r in region if r])  # text block region
    outd["type"] = doc.doctype
    outd["tags"] = doc.all_tags()
    outd["description"] = doc.description
    outd["shelfmarks_historic"] = ";".join([os for os in old_shelfmarks if os])
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
    outd["input_by"] = ";".join(
        sorted(
            list(set([user.get_full_name() or user.username for user in input_users]))
        )
    )  # sorting to ensure deterministic order
    outd["status"] = doc.get_status_display()
    outd["library"] = ";".join(libraries) if any(libraries) else ""
    outd["collection"] = ";".join(collections) if any(collections) else ""

    return outd


from tqdm import tqdm


def export_docs(
    fn="data_export.csv",
    csv_fields=[
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
    ],
):

    # get docs
    docs = get_docs_to_export()

    # save
    with open(fn, "w") as of:
        writer = csv.DictWriter(of, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for doc in track(docs, description=f"Saving data to {fn}"):
            docd = get_export_data_for_doc(doc)
            writer.writerow(docd)
