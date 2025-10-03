from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.fields import TextField
from django.db.models.functions import Concat
from django.forms import ValidationError
from django.forms.models import BaseInlineFormSet
from django.forms.widgets import Textarea, TextInput
from django.urls import path, reverse
from django.utils.html import format_html
from django_admin_inline_paginator_plus.admin import TabularInlinePaginated
from modeltranslation.admin import TabbedTranslationAdmin

from geniza.common.admin import custom_empty_field_list_filter
from geniza.footnotes.metadata_export import AdminFootnoteExporter, AdminSourceExporter
from geniza.footnotes.models import (
    Authorship,
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)


class AuthorshipInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Authorship
    autocomplete_fields = ["creator"]
    fields = ("creator", "sort_order")
    extra = 1


# reusable exception for digital edition footnote validation
DuplicateDigitalEditionsError = ValidationError(
    """
    You cannot create multiple Digital Edition footnotes, or multiple
    Digital Translation footnotes, on the same source and document.
    """,
    code="invalid",
)


class SourceFootnoteInlineFormSet(BaseInlineFormSet):
    """
    Override of the source-footnote inline formset to prevent multiple digital
    ediiton footnotes on the same source and document.
    """

    def clean(self):
        """
        Execute inherited clean method, then validate to ensure no document
        id is repeated across digital edition footnotes.
        """
        super().clean()
        cleaned_data = [form.cleaned_data for form in self.forms if form.is_valid()]
        # get object_id of all digital editions where object type is Document
        if all("object_id" in fn for fn in cleaned_data):
            document_contenttype = ContentType.objects.get(
                app_label="corpus", model="document"
            )
            for digital_relation in [
                Footnote.DIGITAL_EDITION,
                Footnote.DIGITAL_TRANSLATION,
            ]:
                document_pks = [
                    fn.get("object_id")
                    for fn in cleaned_data
                    if digital_relation in fn.get("doc_relation", [])
                    and fn.get("content_type").pk == document_contenttype.pk
                ]
                # if there are any duplicate document pks, it's invalid
                if len(document_pks) > len(set(document_pks)):
                    raise DuplicateDigitalEditionsError


class SourceFootnoteInline(TabularInlinePaginated):
    """Footnote inline for the Source admin"""

    model = Footnote
    fields = (
        "object_link",
        "content_type",
        "object_id",
        "doc_relation",
        "location",
        "emendations",
        "url",
    )
    readonly_fields = ("object_link",)
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }

    per_page = 100

    @admin.display(
        description="object",
    )
    def object_link(self, obj):
        """edit link with string display method for associated content object"""
        # return empty spring for unsaved footnote with no  content object
        if not obj.content_object:
            return ""
        content_obj = obj.content_object
        edit_url = "admin:%s_%s_change" % (
            content_obj._meta.app_label,
            content_obj._meta.model_name,
        )
        edit_path = reverse(edit_url, args=[obj.object_id])
        return format_html(
            f'<a href="{edit_path}">{content_obj} '
            + '<img src="/static/admin/img/icon-changelink.svg" alt="Change"></a>'
        )

    # enable link from inline to edit footnote
    show_change_link = True

    def get_formset(self, request, obj=None, **kwargs):
        """Override TabularInlinePaginated.get_formset to include our
        source-footnote inline formset in the inherited classes"""
        formset_class = super().get_formset(request, obj, **kwargs)

        class PaginationFormSet(SourceFootnoteInlineFormSet, formset_class):
            pass

        return PaginationFormSet


class DocumentFootnoteInlineFormSet(BaseGenericInlineFormSet):
    """
    Override of the document-footnote inline formset to override the clean
    method and raise validation errors.
    """

    def clean(self):
        """
        Override the clean method to raise validation errors preventing
        deletion of a footnote inline with annotations attached, or creation of
        multiple digital edition footnotes on the same source and document,
        """
        super().clean()
        # raise validation error if deleting footnote with associated annos
        valid_forms = [form for form in self.forms if hasattr(form, "cleaned_data")]
        if any(
            [
                form.cleaned_data.get("DELETE")
                and form.instance.annotation_set.count() > 0
                for form in valid_forms
            ]
        ):
            raise ValidationError(
                """
                The footnote selected for deletion has associated
                annotations. If you are sure you want to delete it,
                please do so in the Footnotes section of the admin.
                """,
                code="invalid",
            )

        cleaned_data = [form.cleaned_data for form in valid_forms]
        # get source pk of all digital editions
        if all("source" in fn for fn in cleaned_data):
            for digital_relation in [
                Footnote.DIGITAL_EDITION,
                Footnote.DIGITAL_TRANSLATION,
            ]:
                sources = [
                    fn.get("source").pk
                    for fn in cleaned_data
                    if digital_relation in fn.get("doc_relation", [])
                ]
                # if there are any duplicate source pks, raise validation error
                if len(sources) > len(set(sources)):
                    raise DuplicateDigitalEditionsError


class DocumentFootnoteInline(GenericTabularInline):
    """Footnote inline for the Document admin"""

    model = Footnote
    formset = DocumentFootnoteInlineFormSet
    autocomplete_fields = ["source"]
    fields = (
        "source",
        "doc_relation",
        "location",
        "emendations",
        "notes",
        "url",
    )
    extra = 1
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 3})},
    }
    # enable link from inline to edit footnote
    show_change_link = True


@admin.register(Source)
class SourceAdmin(SortableAdminBase, TabbedTranslationAdmin, admin.ModelAdmin):
    footnote_admin_url = "admin:footnotes_footnote_changelist"

    list_display = ("all_authors", "title", "journal", "volume", "year", "footnotes")
    list_display_links = ("all_authors", "title")
    search_fields = (
        "title",
        "authors__first_name",
        "authors__last_name",
        "year",
        "journal",
        "notes",
        "other_info",
        "languages__name",
        "volume",
    )

    fields = (
        "source_type",
        "title",
        "year",
        "publisher",
        "place_published",
        "edition",
        "journal",
        "volume",
        "issue",
        "page_range",
        "url",
        "other_info",
        "languages",
        "notes",
    )
    list_filter = (
        "source_type",
        "footnote__doc_relation",
        "languages",
        ("authors", admin.RelatedOnlyFieldListFilter),
    )

    inlines = [AuthorshipInline, SourceFootnoteInline]

    class Media:
        css = {"all": ("css/admin-local.css",)}

    def save_related(self, request, form, formsets, change):
        """Override save to ensure slug is generated if empty. Adapted from mep-django"""
        super().save_related(request, form, formsets, change)

        # this must be done after related objects are saved, because generate_slug
        # requires related Creator records
        source = form.instance
        if not source.slug:
            source.generate_slug()
            source.save()

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .metadata_prefetch()
            .footnote_count()
            .filter(
                models.Q(authorship__isnull=True) | models.Q(authorship__sort_order=1)
            )
            .annotate(
                first_author=Concat(
                    "authorship__creator__last_name", "authorship__creator__first_name"
                ),
            )
        )

    @admin.display(description="# footnotes", ordering="footnote__count")
    def footnotes(self, obj):
        return format_html(
            '<a href="{0}?source__id__exact={1!s}">{2}</a>',
            reverse(self.footnote_admin_url),
            str(obj.id),
            obj.footnote__count,
        )

    @admin.display(
        description="Export selected sources to CSV",
    )
    def export_to_csv(self, request, queryset=None):
        """Stream source records as CSV"""
        queryset = queryset or self.get_queryset(request)
        return AdminSourceExporter(
            queryset=queryset, progress=False
        ).http_export_data_csv()

    def get_urls(self):
        """Return admin urls; adds a custom URL for exporting all sources
        as CSV"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="footnotes_source_csv",
            )
        ]
        return urls + super(SourceAdmin, self).get_urls()

    actions = (export_to_csv,)


@admin.register(SourceType)
class SourceTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(SourceLanguage)
class SourceLanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "code")


class DocumentRelationTypesFilter(SimpleListFilter):
    """A custom filter to allow filter footnotes based on
    document relation, no matter how they are used in combination"""

    title = "document relationship"
    parameter_name = "doc_relation"

    def lookups(self, request, model_admin):
        return model_admin.model.DOCUMENT_RELATION_TYPES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(doc_relation__contains=self.value())


class FootnoteForm(forms.ModelForm):
    class Meta:
        model = Footnote
        exclude = ()
        widgets = {
            "location": TextInput(attrs={"size": "10"}),
        }

    def clean(self):
        """
        Raise error on attempted creation of a Digital Edition footnote if one
        already exists on this document and source
        """
        super().clean()
        for digital_relation in [
            Footnote.DIGITAL_EDITION,
            Footnote.DIGITAL_TRANSLATION,
        ]:
            if (
                digital_relation in self.cleaned_data.get("doc_relation", [])
                and Footnote.objects.filter(
                    content_type=self.cleaned_data.get("content_type"),
                    object_id=self.cleaned_data.get("object_id"),
                    source=self.cleaned_data.get("source"),
                    doc_relation__contains=digital_relation,
                )
                .exclude(pk=self.instance.pk)  # exclude self!
                .exists()
            ):
                raise DuplicateDigitalEditionsError


@admin.register(Footnote)
class FootnoteAdmin(admin.ModelAdmin):
    form = FootnoteForm
    list_display = (
        "__str__",
        "source",
        "location",
        "emendations",
        "notes",
        "has_url",
    )
    autocomplete_fields = ["source"]
    list_filter = (
        DocumentRelationTypesFilter,
        (
            "url",
            custom_empty_field_list_filter("url", "Has URL", "No URL"),
        ),
    )
    readonly_fields = ["content_object"]

    search_fields = (
        "source__title",
        "source__authors__first_name",
        "source__authors__last_name",
        "content",
        "emendations",
        "notes",
        "document__id",
        "document__fragments__shelfmark",
    )

    # Add help text to the combination content_type and object_id
    CONTENT_LOOKUP_HELP = """Select the kind of record you want to attach
    a footnote to, and then use the object id search button to select an item."""
    fieldsets = [
        (
            None,
            {
                "fields": ("content_type", "object_id", "content_object"),
                "description": f'<div class="help">{CONTENT_LOOKUP_HELP}</div>',
            },
        ),
        (
            None,
            {
                "fields": (
                    "source",
                    "location",
                    "doc_relation",
                    "url",
                    "emendations",
                    "notes",
                    "content",
                )
            },
        ),
    ]

    class Media:
        css = {"all": ("css/admin-local.css",)}

    def get_queryset(self, request):
        return super().get_queryset(request).metadata_prefetch()

    @admin.display(
        ordering="doc_relation",
        description="Document Relation",
    )
    def doc_relation_list(self, obj):
        # Casting the multichoice object as string to return a reader-friendly
        #  comma-delimited list.
        return str(obj.doc_relation)
        # FIXME: property no longer in use?

    @admin.display(description="Export selected footnotes to CSV")
    def export_to_csv(self, request, queryset=None):
        """Stream footnote records as CSV"""
        queryset = queryset or self.get_queryset(request)
        return AdminFootnoteExporter(
            queryset=queryset, progress=False
        ).http_export_data_csv()

    def get_urls(self):
        """Return admin urls; adds a custom URL for exporting all sources
        as CSV"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="footnotes_footnote_csv",
            )
        ]
        return urls + super(FootnoteAdmin, self).get_urls()

    actions = (export_to_csv,)


@admin.register(Creator)
class CreatorAdmin(TabbedTranslationAdmin):
    list_display = ("last_name", "first_name")
    search_fields = ("first_name", "last_name")
    fields = ("last_name", "first_name")

    class Media:
        css = {"all": ("css/admin-local.css",)}
