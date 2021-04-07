from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
import pytest

from geniza.footnotes.admin import DocumentRelationTypesFilter, FootnoteAdmin,\
    SourceAdmin
from geniza.footnotes.models import Authorship, Creator, Footnote, Source, \
    SourceLanguage, SourceType


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

    @pytest.mark.django_db
    def test_get_queryset(self):
        kernighan = Creator.objects.create(last_name='Kernighan', first_name='Brian')
        ritchie = Creator.objects.create(last_name='Ritchie', first_name='Dennis')
        book = SourceType.objects.get(type='Book')
        cprog = Source.objects.create(
            title='The C Programming Language',
            source_type=book)
        Authorship.objects.create(creator=kernighan, source=cprog)
        Authorship.objects.create(creator=ritchie, source=cprog, sort_order=2)

        # source with no author
        Source.objects.create(title='Unknown', source_type=book)

        # confirm that first author is set correctly on annotated queryset
        qs = SourceAdmin(Source, admin.site).get_queryset('rqst')
        # should return both sources, with or without creator
        assert qs.count() == 2
        # default sort is title; check first author for first source
        assert hasattr(qs.first(), 'first_author')
        assert qs.first().first_author == \
            kernighan.last_name + kernighan.first_name
        # second source has no author
        assert not qs.last().first_author


class TestFootnoteAdmin:

    @pytest.mark.django_db
    def test_doc_relation_list(self):
        fnoteadmin = FootnoteAdmin(Footnote, admin.site)
        book = SourceType.objects.get(type='Book')
        source = Source.objects.create(title='Reader', source_type=book)

        footnote = Footnote(source=source, doc_relation=['E', 'D'])
        assert fnoteadmin.doc_relation_list(footnote) == \
            str(footnote.doc_relation)
