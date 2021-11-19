from unittest.mock import Mock, patch

import pytest
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from geniza.corpus.models import Document
from geniza.footnotes.admin import (
    DocumentRelationTypesFilter,
    FootnoteAdmin,
    SourceAdmin,
    SourceFootnoteInline,
)
from geniza.footnotes.models import Footnote, Source, SourceType


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
                Footnote(doc_relation=[Footnote.EDITION], **footnote_args),
                Footnote(
                    doc_relation=[Footnote.EDITION, Footnote.TRANSLATION],
                    **footnote_args,
                ),
                Footnote(
                    doc_relation=[
                        Footnote.EDITION,
                        Footnote.TRANSLATION,
                        Footnote.DISCUSSION,
                    ],
                    **footnote_args,
                ),
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

    @pytest.mark.django_db
    def test_tabulate_queryset(self, source, twoauthor_source, article):
        source_admin = SourceAdmin(model=Source, admin_site=admin.site)
        qs = source_admin.get_queryset("rqst")

        for source, source_data in zip(qs, source_admin.tabulate_queryset(qs)):
            # test some properties
            assert source.title in source_data
            assert source.journal in source_data
            assert source.year in source_data

            # test compiled data
            for authorship in source.authorship_set.all():
                assert str(authorship.creator) in source_data[1]
            for lang in source.languages.all():
                assert lang.name in source_data[9]

            # none of the fixtures have footnotes, but count should be included
            assert 0 in source_data
            assert (
                f"https://example.com/admin/footnotes/source/{source.id}/change/"
                in source_data
            )

    @pytest.mark.django_db
    @patch("geniza.footnotes.admin.export_to_csv_response")
    def test_export_to_csv(self, mock_export_to_csv_response):
        source_admin = SourceAdmin(model=Source, admin_site=admin.site)
        with patch.object(source_admin, "tabulate_queryset") as tabulate_queryset:
            # if no queryset provided, should use default queryset
            sources = source_admin.get_queryset(Mock())
            source_admin.export_to_csv(Mock())
            assert tabulate_queryset.called_once_with(sources)
            # otherwise should respect the provided queryset
            first_source = Source.objects.first()
            source_admin.export_to_csv(Mock(), first_source)
            assert tabulate_queryset.called_once_with(first_source)

            export_args, export_kwargs = mock_export_to_csv_response.call_args
            # first arg is filename
            csvfilename = export_args[0]
            assert csvfilename.endswith(".csv")
            assert csvfilename.startswith("geniza-sources")
            # should include current date
            assert timezone.now().strftime("%Y%m%d") in csvfilename
            headers = export_args[1]
            assert "source_type" in headers
            assert "authors" in headers
            assert "title" in headers


class TestFootnoteAdmin:
    @pytest.mark.django_db
    def test_doc_relation_list(self):
        fnoteadmin = FootnoteAdmin(Footnote, admin.site)
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title="Reader", source_type=book)

        footnote = Footnote(source=source, doc_relation=["E", "D"])
        assert fnoteadmin.doc_relation_list(footnote) == str(footnote.doc_relation)

    @pytest.mark.django_db
    def test_tabulate_queryset(self, source, document):
        fnoteadmin = FootnoteAdmin(Footnote, admin.site)
        Footnote.objects.create(
            source=source, content_object=document, doc_relation=["E", "D"]
        )
        Footnote.objects.create(
            source=source,
            content_object=document,
            doc_relation=["E"],
            content={"lines": ["some text", "a little more text"]},
        )

        qs = fnoteadmin.get_queryset("rqst")

        for footnote, footnote_data in zip(qs, fnoteadmin.tabulate_queryset(qs)):
            # test some properties
            assert footnote.content_object in footnote_data
            assert footnote.source in footnote_data
            assert footnote.location in footnote_data
            assert footnote.doc_relation in footnote_data
            assert footnote.notes in footnote_data
            assert footnote.url in footnote_data

            if footnote.content:
                assert "\n".join(footnote.content["lines"]) in footnote_data

            assert (
                f"https://example.com/admin/footnotes/footnote/{footnote.id}/change/"
                in footnote_data
            )

    @pytest.mark.django_db
    @patch("geniza.footnotes.admin.export_to_csv_response")
    def test_export_to_csv(self, mock_export_to_csv_response, source, document):
        fnoteadmin = FootnoteAdmin(Footnote, admin.site)
        Footnote.objects.create(
            source=source, doc_relation=["E", "D"], content_object=document
        )
        Footnote.objects.create(
            source=source,
            content_object=document,
            doc_relation=["E"],
            content={"lines": ["some text", "a little more text"]},
        )

        with patch.object(fnoteadmin, "tabulate_queryset") as tabulate_queryset:
            # if no queryset provided, should use default queryset
            footnotes = fnoteadmin.get_queryset(Mock())
            fnoteadmin.export_to_csv(Mock())
            assert tabulate_queryset.called_once_with(footnotes)
            # otherwise should respect the provided queryset
            first_note = Footnote.objects.first()
            fnoteadmin.export_to_csv(Mock(), first_note)
            assert tabulate_queryset.called_once_with(first_note)

            export_args, export_kwargs = mock_export_to_csv_response.call_args
            # first arg is filename
            csvfilename = export_args[0]
            assert csvfilename.endswith(".csv")
            assert csvfilename.startswith("geniza-footnotes")
            # should include current date
            assert timezone.now().strftime("%Y%m%d") in csvfilename
            headers = export_args[1]
            assert "document" in headers
            assert "source" in headers
            assert "content" in headers


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
