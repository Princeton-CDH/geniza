import csv
from collections import namedtuple

from django.shortcuts import render
from django.http import Http404, StreamingHttpResponse
from tabular_export.admin import export_to_csv_response
from django.views.generic.detail import DetailView

from django.db.models import Q
from geniza.corpus.models import Document, TextBlock
from geniza.corpus.admin import DocumentAdmin

from unittest.mock import Mock


class DocumentDetailView(DetailView):

    model = Document

    context_object_name = "document"

    def get_queryset(self, *args, **kwargs):
        """Don't show document if it isn't public"""
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(status=Document.PUBLIC)


# --------------- Publish CSV to sync with old PGP site --------------------- #


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
            ";".join([fn.display() for fn in doc.editions()]),  # editor
        ]


def pgp_metadata_for_old_site(request):
    """A view that streams a large CSV file."""

    queryset = Document.objects.filter(status=Document.PUBLIC).order_by("id")
    # pgpids = [33914, 33760, 33759]
    # queryset = Document.objects.filter(id__in=pgpids)

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
