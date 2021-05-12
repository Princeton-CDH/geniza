from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
import pytest

from geniza.footnotes.admin import (
    DocumentRelationTypesFilter,
    FootnoteAdmin,
    SourceAdmin,
    SourceFootnoteInline,
)
from geniza.footnotes.models import Footnote, Source, SourceType
from geniza.corpus.models import Document


class TestDocumentRelationTypesFilter:
    def test_lookups(self):
        # including params is not currently necessary for the overwritten function
        params = {}

        # GET:<QueryDict: {'Document relation types': ['T']}>
        # <WSGIRequest: GET '/admin/footnotes/footnote/?Document+relation+types=T'>
        request_factory = RequestFactory()
        url = reverse("admin:footnotes_footnote_changelist")
        request = request_factory.get(url, params=params)

        footnote_admin = FootnoteAdmin(model=Footnote, admin_site=admin.site)
        dr_filter = DocumentRelationTypesFilter(
            request, params, Footnote, footnote_admin
        )
        options_list = dr_filter.lookups(request, footnote_admin)

        assert len(options_list) == 3
        assert all([len(opt) == 2 for opt in options_list])
        assert options_list[0][0] == "E"

    @pytest.mark.django_db
    def test_queryset(self, source):
        footnote_args = {
            "source": source,
            "content_type_id": ContentType.objects.get(model="document").id,
            "object_id": 0,
        }

        Footnote.objects.bulk_create(
            [
                Footnote(doc_relation=["E"], **footnote_args),
                Footnote(doc_relation=["E", "T"], **footnote_args),
                Footnote(doc_relation=["E", "D", "T"], **footnote_args),
            ]
        )

        footnote_admin = FootnoteAdmin(model=Footnote, admin_site=admin.site)
        queryset = Footnote.objects.all()

        dr_filter = DocumentRelationTypesFilter(
            None, {"doc_relation": "T"}, Footnote, footnote_admin
        )
        filtered_queryset = dr_filter.queryset(None, queryset)
        assert filtered_queryset.count() == 2

        dr_filter = DocumentRelationTypesFilter(
            None, {"doc_relation": "E"}, Footnote, footnote_admin
        )
        filtered_queryset = dr_filter.queryset(None, queryset)
        assert filtered_queryset.count() == 3

        dr_filter = DocumentRelationTypesFilter(
            None, {"doc_relation": "D"}, Footnote, footnote_admin
        )
        filtered_queryset = dr_filter.queryset(None, queryset)
        assert filtered_queryset.count() == 1


class TestSourceAdmin:
    @pytest.mark.django_db
    def test_get_queryset(self, twoauthor_source):
        # source with no author
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title="Unknown", source_type=book)

        # confirm that first author is set correctly on annotated queryset
        qs = SourceAdmin(Source, admin.site).get_queryset("rqst")
        # should return both sources, with or without creator
        assert qs.count() == 2
        # default sort is title; check first author for first source
        assert hasattr(qs.first(), "first_author")

        first_author = twoauthor_source.authorship_set.first().creator
        assert (
            qs.first().first_author == first_author.last_name + first_author.first_name
        )
        # second source has no author
        assert not qs.last().first_author

        Footnote.objects.create(
            doc_relation=["E"],
            source=source,
            content_type_id=ContentType.objects.get(model="document").id,
            object_id=0,
        )

        qs = SourceAdmin(Source, admin.site).get_queryset("rqst")
        assert hasattr(qs.first(), "footnote__count")

    @pytest.mark.django_db
    def test_footnotes(self):
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title="Unknown", source_type=book)

        source_admin = SourceAdmin(Source, admin.site)
        # manually set footnote__count since it would usually be set in
        #   get_queryset, which is tested above
        source.footnote__count = 1
        html = source_admin.footnotes(source)
        assert f"={source.id}" in html
        assert ">1<" in html


class TestFootnoteAdmin:
    @pytest.mark.django_db
    def test_doc_relation_list(self):
        fnoteadmin = FootnoteAdmin(Footnote, admin.site)
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title="Reader", source_type=book)

        footnote = Footnote(source=source, doc_relation=["E", "D"])
        assert fnoteadmin.doc_relation_list(footnote) == str(footnote.doc_relation)


class TestSourceFootnoteInline:
    @pytest.mark.django_db
    def test_object_link(self):
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title="Unknown", source_type=book)
        footnote = Footnote.objects.create(
            doc_relation=["E"],
            source=source,
            content_type_id=ContentType.objects.get(model="document").id,
            object_id=0,
        )
        doc = Document.objects.create()
        doc.footnotes.add(footnote)

        inline = SourceFootnoteInline(Source, admin_site=admin.site)
        doc_link = inline.object_link(footnote)

        assert str(doc.id) in doc_link
        assert str(doc) in doc_link
