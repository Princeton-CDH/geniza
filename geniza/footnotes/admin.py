from adminsortable2.admin import SortableInlineAdminMixin
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.postgres.aggregates import ArrayAgg
from django.db import models
from django.db.models import Count
from django.db.models.functions import Concat
from django.urls import resolve, reverse
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin

from geniza.footnotes.models import (
    Authorship,
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)
from geniza.common.admin import custom_empty_field_list_filter


class AuthorshipInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Authorship
    autocomplete_fields = ["creator"]
    fields = ("creator", "sort_order")
    extra = 1


@admin.register(Source)
class SourceAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    footnote_admin_url = "admin:footnotes_footnote_changelist"

    list_display = ("all_authors", "title", "volume", "year", "footnotes")

    search_fields = ("title", "authors__first_name", "authors__last_name", "year")

    fields = ("source_type", "title", "year", "edition", "volume", "languages", "notes")
    list_filter = ("source_type", "authors")

    inlines = [AuthorshipInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(
                models.Q(authorship__isnull=True) | models.Q(authorship__sort_order=1)
            )
            .annotate(
                Count("footnote", distinct=True),
                first_author=Concat(
                    "authorship__creator__last_name", "authorship__creator__first_name"
                ),
            )
        )

    def footnotes(self, obj):
        return format_html(
            '<a href="{0}?source__id__exact={1!s}">{2}</a>',
            reverse(self.footnote_admin_url),
            str(obj.id),
            obj.footnote__count,
        )

    footnotes.short_description = "# footnotes"
    footnotes.admin_order_field = "footnote__count"


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


@admin.register(Footnote)
class FootnoteAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "content_object",
        "doc_relation_list",
        "location",
        "notes",
        "has_transcription",
    )
    list_filter = (
        DocumentRelationTypesFilter,
        (
            "content",
            custom_empty_field_list_filter(
                "transcription", "Has transcription", "No transcription"
            ),
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
                    "notes",
                )
            },
        ),
    ]

    def doc_relation_list(self, obj):
        # Casting the multichoice object as string to return a reader-friendly
        #  comma-delimited list.
        return str(obj.doc_relation)

    doc_relation_list.short_description = "Document Relation"
    doc_relation_list.admin_order_field = "doc_relation"


class FootnoteInline(GenericTabularInline):
    model = Footnote
    autocomplete_fields = ["source"]
    fields = (
        "source",
        "location",
        "doc_relation",
        "notes",
    )
    extra = 1


@admin.register(Creator)
class CreatorAdmin(TabbedTranslationAdmin):
    list_display = ("last_name", "first_name")
    search_fields = ("first_name", "last_name")
    fields = ("last_name", "first_name")
