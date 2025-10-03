from unittest.mock import Mock, patch

import pytest
from django.contrib import admin
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.admin import (
    DocumentFootnoteInlineFormSet,
    DocumentRelationTypesFilter,
    DuplicateDigitalEditionsError,
    FootnoteAdmin,
    FootnoteForm,
    SourceAdmin,
    SourceFootnoteInline,
)
from geniza.footnotes.metadata_export import FootnoteExporter
from geniza.footnotes.models import Authorship, Creator, Footnote, Source, SourceType


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

        assert len(options_list) == 5
        assert all([len(opt) == 2 for opt in options_list])
        assert options_list[0][0] == "E"

    @pytest.mark.django_db
    def test_queryset(self, source):
        footnote_args = {
            "source": source,
            "content_type_id": ContentType.objects.get(
                app_label="corpus", model="document"
            ).id,
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
    def test_save_related(self, source):
        # if a source does not have a slug, the form should generate one after related_save
        new_source = Source.objects.create(title="test", source_type=source.source_type)
        assert not new_source.slug

        # mock all arguments to admin method; form.instance should be our source
        mockform = Mock()
        mockform.instance = new_source
        with patch.object(admin.ModelAdmin, "save_related"):
            SourceAdmin(Source, Mock()).save_related(Mock(), mockform, Mock(), Mock())
        assert new_source.slug

        # should generate slug only after new related creators are saved
        creator_source = Source.objects.create(
            title="test", source_type=source.source_type
        )

        mockform = Mock()
        mockform.instance = creator_source

        with patch.object(admin.ModelAdmin, "save_related") as super_save_related:

            def save_related(obj, request, form, formsets):
                # simulate django saving the related objects and relationships
                creator = Creator.objects.create(first_name="SD", last_name="Goitein")
                Authorship.objects.create(creator=creator, source=creator_source)

            super_save_related.side_effect = save_related

            SourceAdmin(Source, Mock()).save_related(Mock(), mockform, Mock(), Mock())

        # the slug should reflect that the Creator exists
        assert "goitein" in creator_source.slug

    @pytest.mark.django_db
    def test_get_queryset(self, twoauthor_source):
        # source with no author
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title_en="Unknown", source_type=book)

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
            content_type_id=ContentType.objects.get(
                app_label="corpus", model="document"
            ).id,
            object_id=0,
        )

        qs = SourceAdmin(Source, admin.site).get_queryset("rqst")
        assert hasattr(qs.first(), "footnote__count")

    @pytest.mark.django_db
    def test_footnotes(self):
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title_en="Unknown", source_type=book)

        source_admin = SourceAdmin(Source, admin.site)
        # manually set footnote__count since it would usually be set in
        #   get_queryset, which is tested above
        source.footnote__count = 1
        html = source_admin.footnotes(source)
        assert f"={source.id}" in html
        assert ">1<" in html

    @pytest.mark.django_db
    def test_export_to_csv(self, source, twoauthor_source):
        source_admin = SourceAdmin(Source, admin.site)
        response = source_admin.export_to_csv(Mock())
        # consume the binary streaming content and decode to inspect as str
        content = b"".join([val for val in response.streaming_content]).decode()

        # spot-check that we get expected data
        # - header row
        assert "source_type,authors,title" in content
        # - some content
        assert str(source.source_type) in content
        assert source.title in content
        assert str(twoauthor_source.source_type) in content
        assert twoauthor_source.title in content


class TestFootnoteAdmin:
    @pytest.mark.django_db
    def test_doc_relation_list(self):
        fnoteadmin = FootnoteAdmin(Footnote, admin.site)
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title_en="Reader", source_type=book)

        footnote = Footnote(
            source=source, doc_relation=[Footnote.EDITION, Footnote.DISCUSSION]
        )
        assert fnoteadmin.doc_relation_list(footnote) == str(footnote.doc_relation)

    @pytest.mark.django_db
    def test_export_to_csv(self, source, document):
        fnoteadmin = FootnoteAdmin(Footnote, admin.site)
        # create footnotes for our source & document to export
        fnote1 = Footnote.objects.create(
            source=source,
            doc_relation=[Footnote.EDITION, Footnote.DISCUSSION],
            content_object=document,
        )
        fnote2 = Footnote.objects.create(
            source=source,
            content_object=document,
            doc_relation=[Footnote.DIGITAL_EDITION],
            url="http://example.com/some/digital/edition.pdf",
            notes="amendations by AE",
        )

        response = fnoteadmin.export_to_csv(Mock())  # mock request, unused
        # consume the binary streaming content and decode to inspect as str
        content = b"".join([val for val in response.streaming_content]).decode()

        # spot-check that we get expected data
        # - header row
        assert "document,document_id,source" in content
        # - some content
        assert str(document) in content
        assert str(document.pk) in content
        assert str(source) in content
        assert fnote2.notes in content
        assert fnote2.url in content
        for fnote in [fnote1, fnote2]:
            doc_relation_list = fnote.get_doc_relation_list()
            separator = FootnoteExporter.sep_within_cells
            assert separator.join(doc_relation_list) in content
            assert (
                reverse("admin:footnotes_footnote_change", args=[fnote.pk]) in content
            )


class TestSourceFootnoteInline:
    @pytest.mark.django_db
    def test_object_link(self):
        book = SourceType.objects.get(type="Book")
        source = Source.objects.create(title_en="Unknown", source_type=book)
        footnote = Footnote.objects.create(
            doc_relation=["E"],
            source=source,
            content_type_id=ContentType.objects.get(
                app_label="corpus", model="document"
            ).id,
            object_id=0,
        )
        doc = Document.objects.create()
        doc.footnotes.add(footnote)

        inline = SourceFootnoteInline(Source, admin_site=admin.site)
        doc_link = inline.object_link(footnote)

        assert str(doc.id) in doc_link
        assert str(doc) in doc_link


class TestSourceFootnoteInlineFormSet:
    def test_clean(self, document, source, admin_client):
        doc_contenttype = ContentType.objects.get(app_label="corpus", model="document")
        # should raise validation error if two digital editions on the same document
        response = admin_client.post(
            reverse("admin:footnotes_source_change", args=(source.id,)),
            data={
                "footnote_set-INITIAL_FORMS": ["0"],
                "footnote_set-TOTAL_FORMS": ["2"],
                "footnote_set-MAX_NUM_FORMS": ["1000"],
                "footnote_set-0-source": [str(source.pk)],
                "footnote_set-0-content_type": [str(doc_contenttype.pk)],
                "footnote_set-0-object_id": [str(document.pk)],
                "footnote_set-0-doc_relation": [Footnote.DIGITAL_EDITION],
                "footnote_set-1-source": [str(source.pk)],
                "footnote_set-1-content_type": [str(doc_contenttype.pk)],
                "footnote_set-1-object_id": [str(document.pk)],
                "footnote_set-1-doc_relation": [Footnote.DIGITAL_EDITION],
            },
        )
        assertContains(response, DuplicateDigitalEditionsError.message)


class TestDocumentFootnoteInlineFormSet:
    def test_clean(self, document, source, admin_client):
        # should raise error if trying to delete a footnote with annotations
        doc_contenttype = ContentType.objects.get(app_label="corpus", model="document")
        fn = Footnote.objects.create(
            source=source,
            object_id=document.id,
            content_type=doc_contenttype,
        )
        Annotation.objects.create(footnote=fn, content={})
        FootnoteInlineFormSet = generic_inlineformset_factory(
            Footnote, exclude=[], formset=DocumentFootnoteInlineFormSet
        )
        data = {
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 1,
            "form-0-id": fn.id,
            "form-0-source": source.pk,
            "form-0-DELETE": True,
        }
        formset = FootnoteInlineFormSet(instance=document, prefix="form", data=data)
        with pytest.raises(ValidationError):
            formset.clean()

        # should raise error if two digital editions on the same source
        data = {
            "image_overrides": "{}",  # in real life, will be auto-populated by django admin
            "footnotes-footnote-content_type-object_id-TOTAL_FORMS": ["2"],
            "footnotes-footnote-content_type-object_id-0-source": [str(source.pk)],
            "footnotes-footnote-content_type-object_id-0-doc_relation": [
                Footnote.DIGITAL_EDITION,
            ],
            "footnotes-footnote-content_type-object_id-1-source": [str(source.pk)],
            "footnotes-footnote-content_type-object_id-1-doc_relation": [
                Footnote.DIGITAL_EDITION
            ],
        }
        response = admin_client.post(
            reverse("admin:corpus_document_change", args=(document.id,)), data
        )
        assertContains(response, DuplicateDigitalEditionsError.message)

        # edition should be fine
        data = {
            **data,
            "footnotes-footnote-content_type-object_id-1-doc_relation": [
                Footnote.EDITION
            ],
        }
        response = admin_client.post(
            reverse("admin:corpus_document_change", args=(document.id,)), data
        )
        assertNotContains(response, DuplicateDigitalEditionsError.message)


class TestFootnoteForm:
    def test_clean(self, source, document):
        # should be invalid when trying to create another digital edition on
        # the same source and document
        doc_contenttype = ContentType.objects.get(app_label="corpus", model="document")
        footnote = Footnote.objects.create(
            source=source,
            content_object=document,
            content_type=doc_contenttype,
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        form = FootnoteForm(
            data={
                "doc_relation": footnote.doc_relation,
                "content_type": footnote.content_type,
                "object_id": footnote.object_id,
                "source": footnote.source,
            }
        )
        assert not form.is_valid()

        # edition should be fine, though!
        form = FootnoteForm(
            data={
                "doc_relation": [Footnote.EDITION],
                "content_type": footnote.content_type,
                "object_id": footnote.object_id,
                "source": footnote.source,
            }
        )
        assert form.is_valid()
