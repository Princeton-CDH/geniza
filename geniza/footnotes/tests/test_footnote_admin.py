import pytest

from django.contrib import admin
from django.test import TestCase, RequestFactory
from django.urls import reverse

from geniza.footnotes.admin import SourceAdmin, DocumentRelationsFilter
from geniza.footnotes.models import Source
from geniza.people.models import Person
from geniza.footnotes.models import SourceType, Source
from geniza.corpus.models import LanguageScript

@pytest.mark.skip('Waiting to move document relations filter to footnotes')
class TestDocumentRelationsFilter:
    def test_lookups(self):
        # including params is not currently necessary for the overwritten function
        params = {}

        # GET:<QueryDict: {'Document relation': ['T']}> 
        # <WSGIRequest: GET '/admin/footnotes/source/?Document+relation=T'>
        request_factory = RequestFactory()
        url = reverse('admin:footnotes_source_changelist')
        request = request_factory.get(url, params=params)

        source_admin = SourceAdmin(model=Source, admin_site=admin.site)
        dr_filter = DocumentRelationsFilter(request, params, Source, source_admin)
        options_list = dr_filter.lookups(request, source_admin)
        
        assert len(options_list) == 3
        assert all([len(opt) == 2 for opt in options_list])
        assert options_list[0][0] == 'E'

    @pytest.mark.django_db
    def test_queryset(self):
        # Create many sources
        orwell = Person.objects.create(first_name='George', last_name='Orwell')
        essay = SourceType.objects.create(type='Essay')
        english = LanguageScript.objects.create(language='English', script='English')
        source_kwargs = {
            'author': orwell, 'title': 'A Nice Cup of Tea', 
            'source_type': essay, 'language': english
        }
        Source.objects.bulk_create([
            Source(document_relations=['E', 'T'], **source_kwargs),
            Source(document_relations=['E'], **source_kwargs),
            Source(document_relations=['D'], **source_kwargs),
            Source(document_relations=['T', 'D'], **source_kwargs)
        ])

        # Ensure that the querysets output is appropriate
        # See explanation above for details
        params = {'Document relation': ['T']}
        request_factory = RequestFactory()
        url = reverse('admin:footnotes_source_changelist')
        request = request_factory.get(url, params=params)

        source_admin = SourceAdmin(model=Source, admin_site=admin.site)
        dr_filter = DocumentRelationsFilter(request, params, Source, source_admin)

        queryset = Source.objects.all()
        filtered_queryset = dr_filter.queryset(request, queryset)


class TestSourceAdmin:
    def test_join_document_relations(self):
        pass

    def test_get_publish_date_year(self):
        pass