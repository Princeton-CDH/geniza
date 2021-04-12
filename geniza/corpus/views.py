from django.shortcuts import render
from django.views.generic.detail import DetailView

from geniza.corpus.models import Document

class DocumentDetailView(DetailView):

    model = Document

    context_object_name = 'document'