from django.shortcuts import render
from django.http import Http404
from django.views.generic.detail import DetailView

from geniza.corpus.models import Document

class DocumentDetailView(DetailView):

    model = Document

    context_object_name = 'document'

    def get(self, *args, **kwargs):
        '''Don't show document if it isn't public'''
        if self.get_object().status != Document.PUBLIC:
            raise Http404("Document does not exist")
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        '''Find all variables listed in the template'''
        context = super().get_context_data(**kwargs)
        
        this_document = self.get_object()
        property_list = ['description', 'doctype',
            'tag_list', 'all_languages', 'shelfmark',
            'last_modified', 'language_note']

        context['document_dict'] = {
            attr: getattr(this_document, attr) for attr in property_list if 
                getattr(this_document, attr)
        }
        return context