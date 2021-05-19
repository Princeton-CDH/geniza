from django.views.generic import DetailView, ListView

# from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin

from geniza.corpus.forms import DocumentSearchForm
from geniza.corpus.models import Document
from geniza.corpus.solr_queryset import DocumentSolrQuerySet


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

        # return 50 documents for now; pagination TODO
        return documents[:50]


class DocumentDetailView(DetailView):

    model = Document

    context_object_name = "document"

    def get_queryset(self, *args, **kwargs):
        """Don't show document if it isn't public"""
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(status=Document.PUBLIC)
