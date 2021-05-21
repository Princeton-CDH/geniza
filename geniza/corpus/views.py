import csv
from collections import namedtuple

from django.shortcuts import render
from django.http import Http404, StreamingHttpResponse
from tabular_export.admin import export_to_csv_response
from django.views.generic.detail import DetailView

from django.db.models import Q
from geniza.corpus.models import Document, TextBlock
from geniza.corpus.admin import DocumentAdmin
from geniza.footnotes.models import Footnote

from unittest.mock import Mock


class DocumentDetailView(DetailView):

    model = Document

    context_object_name = "document"

    def get_queryset(self, *args, **kwargs):
        """Don't show document if it isn't public"""
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(status=Document.PUBLIC)


# --------------- Publish CSV to sync with old PGP site --------------------- #


def parse_edition_string(editions):
    if editions:
        edition_list = [
            "trans. " + fn.display().strip(".")
            if Footnote.TRANSLATION in fn.doc_relation
            else "ed. " + fn.display().strip(".")
            for fn in editions
        ]

        edition_list = [
            s + f" {fn.url}" if fn.url else s for s, fn in zip(edition_list, editions)
        ]

        return_str = "; also ".join(edition_list)

        # TODO: omg there *has* to be a better way to just capitalize the first
        #  letter of a string in python.
        return return_str[0].upper() + return_str[1:] + "."
    return ""


def tabulate_queryset(queryset):

    for doc in queryset:
        primary_fragment = doc.textblock_set.first().fragment

        yield [
            doc.id,  # pgpid
            primary_fragment.collection,  # library
            primary_fragment.shelfmark,  # shelfmark
            primary_fragment.old_shelfmarks,  # shelfmark_alt
            doc.textblock_set.first().get_side_display(),  # rectoverso
            doc.doctype,  # type
            doc.all_tags(),  # tags
            doc.shelfmark if " + " in doc.shelfmark else "",  # joins
            doc.description,  # descr
            parse_edition_string(doc.editions()),  # editor
        ]


def pgp_metadata_for_old_site(request):
    """A view that streams a large CSV file."""

    queryset = Document.objects.filter(status=Document.PUBLIC).order_by("id")

    # return response
    return export_to_csv_response(
        DocumentAdmin.csv_filename(DocumentAdmin),
        [
            "pgpid",
            "library",
            "shelfmark",
            "shelfmark_alt",
            "rectoverso",
            "type",
            "tags",
            "joins",
            "descr",
            "editor",
        ],
        tabulate_queryset(queryset),
    )


# --------------------------------------------------------------------------- #
