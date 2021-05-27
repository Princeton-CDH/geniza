from django.db.models.query import Prefetch
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormMixin
from tabular_export.admin import export_to_csv_response

from geniza.corpus.forms import DocumentSearchForm
from geniza.corpus.models import Document, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.footnotes.models import Footnote


class DocumentSearchView(ListView, FormMixin):
    model = Document
    form_class = DocumentSearchForm
    context_object_name = "documents"
    template_name = "corpus/document_list.html"

    # map form sort to solr sort field
    solr_sort = {
        "relevance": "-score",
        #        'name': 'sort_name_isort'
    }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # use GET instead of default POST/PUT for form data
        form_data = self.request.GET.copy()

        # always use relevance sort for keyword search;
        # otherwise use default (sort by name)
        if form_data.get("query", None):
            form_data["sort"] = "relevance"
        # else:
        # form_data['sort'] = self.initial['sort']

        # use initial values as defaults
        # for key, val in self.initial.items():
        # form_data.setdefault(key, val)

        kwargs["data"] = form_data
        return kwargs

    def get_queryset(self):
        documents = DocumentSolrQuerySet()
        form = self.get_form()
        # return empty queryset if not valid
        if not form.is_valid():
            documents = documents.none()

        # when form is valid, check for search term and filter queryset
        else:
            search_opts = form.cleaned_data

            if search_opts["query"]:
                documents = documents.keyword_search(search_opts["query"]).also(
                    "score"
                )  # include relevance score in results

            # sorting TODO
            # order based on solr name for search option
            # documents = documents.order_by(self.solr_sort[search_opts['sort'] ])

        self.queryset = documents

        # return 50 documents for now; pagination TODO
        return documents[:50]

    def get_context_data(self):
        context_data = super().get_context_data()
        # should eventually be handled by paginator, but
        # patch in total number of results for display for now
        context_data.update(
            {
                "total": self.queryset.count(),
            }
        )
        return context_data


class DocumentDetailView(DetailView):
    """public display of a single :class:`~geniza.corpus.models.Document`"""

    model = Document

    context_object_name = "document"

    def get_queryset(self, *args, **kwargs):
        """Don't show document if it isn't public"""
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(status=Document.PUBLIC)


# --------------- Publish CSV to sync with old PGP site --------------------- #


def old_pgp_edition(editions):
    """output footnote and source information in a format similar to
    old pgp metadata editor/editions."""
    if editions:
        # label as translation if edition also supplies translation;
        # include url if any
        edition_list = [
            "%s%s%s"
            % (
                "and trans. " if Footnote.TRANSLATION in fn.doc_relation else "",
                fn.display().strip("."),
                " %s" % fn.url if fn.url else "",
            )
            for fn in editions
        ]
        # combine multiple editons as Ed. ...; also ed. ...
        return "".join(["Ed. ", "; also ed. ".join(edition_list), "."])

    return ""


def old_pgp_tabulate_data(queryset):
    """Takes a :class:`~geniza.corpus.models.Document` queryset and
    yields rows of data for serialization as csv in :method:`pgp_metadata_for_old_site`"""
    # NOTE: This logic assumes that documents will always have a fragment
    for doc in queryset:
        primary_fragment = doc.textblock_set.first().fragment
        # combined shelfmark was included in the join column previously
        join_shelfmark = doc.shelfmark
        # library abbreviation; use collection abbreviation as fallback
        library = ""
        if primary_fragment.collection:
            library = (
                primary_fragment.collection.lib_abbrev
                or primary_fragment.collection.abbrev
            )

        yield [
            doc.id,  # pgpid
            library,  # library / collection
            primary_fragment.shelfmark,  # shelfmark
            primary_fragment.old_shelfmarks,  # shelfmark_alt
            doc.textblock_set.first().get_side_display(),  # recto_verso
            doc.doctype,  # document type
            " ".join("#" + t.name for t in doc.tags.all()),  # tags
            join_shelfmark if " + " in join_shelfmark else "",  # join
            doc.description,  # description
            old_pgp_edition(doc.editions()),  # editor
        ]


def pgp_metadata_for_old_site(request):
    """Stream metadata in CSV format for index and display in the old PGP site."""

    # limit to documents with associated fragments, since the output
    # assumes a document has at least one frgment
    queryset = (
        Document.objects.filter(status=Document.PUBLIC, fragments__isnull=False)
        .order_by("id")
        .distinct()
        .select_related("doctype")
        .prefetch_related(
            "tags",
            "footnotes",
            # see corpus admin for notes on nested prefetch
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment", "fragment__collection"
                ),
            ),
        )
    )
    # return response
    return export_to_csv_response(
        "pgp_metadata.csv",
        [
            "pgpid",
            "library",
            "shelfmark",
            "shelfmark_alt",
            "recto_verso",
            "type",
            "tags",
            "joins",
            "description",
            "editor",
        ],
        old_pgp_tabulate_data(queryset),
    )


# --------------------------------------------------------------------------- #
