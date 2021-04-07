import pytest

from django.contrib import admin
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType

from geniza.footnotes.admin import FootnoteAdmin, SourceAdmin, DocumentRelationTypesFilter
from geniza.footnotes.models import Creator, Footnote, Source, SourceLanguage,\
    SourceType


class TestDocumentRelationTypesFilter:

    def test_lookups(self):
        # including params is not currently necessary for the overwritten function
        params = {}

        # GET:<QueryDict: {'Document relation types': ['T']}>
        # <WSGIRequest: GET '/admin/footnotes/footnote/?Document+relation+types=T'>
        request_factory = RequestFactory()
        url = reverse('admin:footnotes_footnote_changelist')
        request = request_factory.get(url, params=params)

        footnote_admin = FootnoteAdmin(model=Footnote, admin_site=admin.site)
        dr_filter = DocumentRelationTypesFilter(request, params, Footnote, footnote_admin)
        options_list = dr_filter.lookups(request, footnote_admin)

        assert len(options_list) == 3
        assert all([len(opt) == 2 for opt in options_list])
        assert options_list[0][0] == 'E'

    @pytest.mark.django_db
    def test_queryset(self):
        # Create many sources
        orwell = Creator.objects.create(
            last_name='Orwell', first_name='George')
        essay = SourceType.objects.create(type='Essay')
        english = SourceLanguage.objects.get(name='English')
        source = Source.objects.create(
            title='A Nice Cup of Tea', source_type=essay)
        source.languages.add(english)
        source.creators.add(orwell)

        footnote_args = {
            'source': source,
            'content_type_id': ContentType.objects.get(model='document').id,
            'object_id': 0
        }

        Footnote.objects.bulk_create([
            Footnote(doc_relation=['E'], **footnote_args),
            Footnote(doc_relation=['E', 'T'], **footnote_args),
            Footnote(doc_relation=['E', 'D', 'T'], **footnote_args),
        ])

        footnote_admin = FootnoteAdmin(model=Footnote, admin_site=admin.site)
        queryset = Footnote.objects.all()

        dr_filter = DocumentRelationTypesFilter(
            None, {'doc_relation': 'T'}, Footnote, footnote_admin)
        filtered_queryset = dr_filter.queryset(None, queryset)
        assert filtered_queryset.count() == 2

        dr_filter = DocumentRelationTypesFilter(
            None, {'doc_relation': 'E'}, Footnote, footnote_admin)
        filtered_queryset = dr_filter.queryset(None, queryset)
        assert filtered_queryset.count() == 3

        dr_filter = DocumentRelationTypesFilter(
            None, {'doc_relation': 'D'}, Footnote, footnote_admin)
        filtered_queryset = dr_filter.queryset(None, queryset)
        assert filtered_queryset.count() == 1


class TestSourceAdmin:
    def test_join_document_relations(self):
        pass
