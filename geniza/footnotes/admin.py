from adminsortable2.admin import SortableInlineAdminMixin
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.admin import GenericTabularInline
from modeltranslation.admin import TabbedTranslationAdmin

from geniza.footnotes.models import Authorship, Creator, Footnote, Source, \
    SourceLanguage, SourceType


class AuthorshipInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Authorship
    autocomplete_fields = ['creator']
    fields = ('creator', 'sort_order')
    extra = 1


@admin.register(Source)
class SourceAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    list_display = (
        'title', 'all_creators',
        'year',
        'edition',
    )

    search_fields = (
        'title', 'creators__first_name', 'creators__last_name' 'year'
    )

    fields = (
        'source_type',
        'title', 'year',
        'edition', 'volume', 'page_range',
        'language'
    )

    inlines = [AuthorshipInline]


@admin.register(SourceType)
class SourceTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(SourceLanguage)
class SourceLanguageAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')


class DocumentRelationTypesFilter(SimpleListFilter):
    '''A custom filter that allows us to filter sources if any of a source's
     document relations match the given facet'''

    title = 'document relation types'
    parameter_name = 'document_relation_types'

    def lookups(self, request, model_admin):
        return model_admin.model.DOCUMENT_RELATION_TYPES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(document_relation_types__contains=self.value())


@admin.register(Footnote)
class FootnoteAdmin(admin.ModelAdmin):
    list_display = (
        'source', 'page_range', 'get_document_relation_types', 'content_object'
    )

    list_filter = (
        DocumentRelationTypesFilter,
    )

    # Add help text to the combination content_type and object_id
    CONTENT_LOOKUP_HELP = '''Select the kind of record you want to attach
    a footnote to, and then use the object id search button to select an item.'''
    fieldsets = [
        (None, {
            'fields': ('content_type', 'object_id'),
            'description': f'<div class="help">{CONTENT_LOOKUP_HELP}</div>'
        }),
        (None, {
            'fields': (
                'source', 'page_range', 'document_relation_types',
                'notes'
            )
        })
    ]

    def get_document_relation_types(self, obj):
        # Casting the multichoice object as a string will return a reader-friendly
        #  comma-delimited list.
        return str(obj.document_relation_types)
    get_document_relation_types.short_description = 'Document Relation Types'


class FootnoteInline(GenericTabularInline):
    model = Footnote
    autocomplete_fields = ['source']
    fields = ('source', 'page_range', 'document_relation_types', 'notes',)
    extra = 1


@admin.register(Creator)
class CreatorAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    list_display = ('first_name', 'last_name')
    search_fields = ('first_name', 'last_name')
