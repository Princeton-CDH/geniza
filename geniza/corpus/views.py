from django.shortcuts import render
from django.views.generic.detail import DetailView

from geniza.corpus.models import Document

class DocumentDetailView(DetailView):

    model = Document

    context_object_name = 'document'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        this_document = self.get_object()
        property_list = ['description', 'doctype',
            'tag_list', 'all_languages', 'collection', 'shelfmark',
            'last_modified', 'language_note']

        context['document_dict'] = {
            attr: getattr(this_document, attr) for attr in property_list if 
                getattr(this_document, attr)
        }
        return context