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
