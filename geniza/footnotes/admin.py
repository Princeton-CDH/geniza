from adminsortable2.admin import SortableInlineAdminMixin
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.db import models
from django.db.models.fields import CharField, TextField
from django.db.models.functions import Concat
from django.forms import ValidationError
from django.forms.widgets import Textarea, TextInput
from django.urls import path, reverse
from django.utils.html import format_html
from django_admin_inline_paginator.admin import TabularInlinePaginated
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


class SourceFootnoteInline(TabularInlinePaginated):
    """Footnote inline for the Source admin"""

    model = Footnote
    fields = (
        "object_link",
        "content_type",
        "object_id",
        "doc_relation",
        "location",
        "url",
    )
    readonly_fields = ("object_link",)
    formfield_overrides = {
        CharField: {"widget": TextInput(attrs={"size": "10"})},
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


class FootnoteInlineFormSet(BaseGenericInlineFormSet):
    """
    Override of the inline formset to prevent deletion of a footnote inline if
    it has annotations attached.
    """

    def clean(self):
        super().clean()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            data = form.cleaned_data

            if data.get("DELETE") and form.instance.annotation_set.count() > 0:
                raise ValidationError(
                    """
                    The footnote selected for deletion has associated
                    annotations. If you are sure you want to delete it,
                    please do so in the Footnotes section of the admin.
                    """,
                    code="invalid",
                )


class DocumentFootnoteInline(GenericTabularInline):
    """Footnote inline for the Document admin"""

    model = Footnote
    formset = FootnoteInlineFormSet
    autocomplete_fields = ["source"]
    fields = (
        "source",
        "doc_relation",
        "location",
        "notes",
        "url",
    )
    extra = 1
    formfield_overrides = {
        CharField: {"widget": TextInput(attrs={"size": "10"})},
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }
    # enable link from inline to edit footnote
    show_change_link = True


@admin.register(Source)
class SourceAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
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


@admin.register(Footnote)
class FootnoteAdmin(admin.ModelAdmin):
    form = FootnoteForm
    list_display = (
        "__str__",
        "source",
        "location",
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
