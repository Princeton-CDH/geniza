from django.shortcuts import render
from django.http import Http404
from django.views.generic.detail import DetailView

from geniza.corpus.models import Document

class DocumentDetailView(DetailView):

    model = Document

    context_object_name = 'document'

    def get_queryset(self, *args, **kwargs):
        '''Don't show document if it isn't public'''
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(status=Document.PUBLIC)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        this_document = self.get_object()

        # concatenate all tags
        context['tags'] = ['#' + str(tag) for tag in this_document.tags.all()]
        
        return context
