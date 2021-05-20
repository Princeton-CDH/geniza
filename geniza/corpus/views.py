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


DocumentRow = namedtuple(
    "DocumentRow",
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
)


def tabulate_queryset(queryset):
    reverse_recto_verso_lookup = {
        code: label.lower() for code, label in TextBlock.RECTO_VERSO_CHOICES
    }

    for doc in queryset:
        all_fragments = doc.fragments.all()
        rectoverso_q = doc.textblock_set.filter(~Q(side="")).first()

        row = DocumentRow(
            **{
                "pgpid": doc.id,
                "library": all_fragments.first().collection,
                "shelfmark": all_fragments.first().shelfmark,
                "shelfmark_alt": all_fragments.first().old_shelfmarks,
                "rectoverso": reverse_recto_verso_lookup.get(
                    rectoverso_q.side if rectoverso_q else ""
                ),
                "type": doc.doctype,
                "tags": doc.all_tags(),
                "joins": doc.shelfmark if " + " in doc.shelfmark else "",
                "descr": doc.description,
                "editor": "",
            }
        )

        yield row


def render_pgp_metadata_for_old_site(request):
    """A view that streams a large CSV file."""

    # queryset = Document.objects.filter(status=Document.PUBLIC)
    foo = [33914, 33760, 33759]
    queryset = Document.objects.filter(id__in=foo)

    queryset = queryset.order_by("id")

    # return response
    return export_to_csv_response(
        DocumentAdmin.csv_filename(DocumentAdmin),
        DocumentRow._fields,
        tabulate_queryset(queryset),
    )


# --------------------------------------------------------------------------- #
