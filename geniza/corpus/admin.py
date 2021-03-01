from django.contrib import admin

from django.utils.html import format_html
from django.urls import reverse

from geniza.corpus.models import Collection, Document, DocumentType, \
    Fragment, LanguageScript, TextBlock


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('abbrev', 'library', 'location', 'collection')
    search_fields = ('library', 'location', 'collection')


@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = ('language', 'script', 'display_name', 'usage_count')

    def usage_count(self, obj):
        admin_link_url = 'admin:corpus_document_changelist'
        return format_html(
            '<a href="{0}?languages__id__exact={1!s}" target="_blank">{2}</a>',
            reverse(admin_link_url), str(obj.id),
            obj.document_set.count()
        )

class TextBlockInline(admin.TabularInline):
    model = TextBlock
    autocomplete_fields = ['fragment']
    readonly_fields = ('thumbnail', )
    fields = ('fragment', 'side', 'extent_label', 'order',
              'thumbnail')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'shelfmark', 'description', 'doctype',
        'tag_list', 'all_languages', 'is_textblock',
        'last_modified'
    )
    readonly_fields = ('old_input_by', 'old_input_date',
                       'created', 'last_modified', 'shelfmark')
    search_fields = ('fragments__shelfmark', 'tags__name', 'description',
                     'old_input_by')
    # TODO include search on edition once we add footnotes

    list_filter = (
        'doctype', 'languages', 'textblock__extent_label',
    )

    fields = (
        'shelfmark',
        'doctype',
        'languages',
        'description',
        'tags',
        # edition, translation
        'notes',
        # text block
        ('old_input_by', 'old_input_date'),
        ('created', 'last_modified')
    )
    filter_horizontal = ('languages', )
    inlines = [
        TextBlockInline,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .prefetch_related('tags', 'languages', 'textblock_set')


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    list_display = ('shelfmark', 'collection', 'url',
                    'is_multifragment')
    search_fields = ('shelfmark', 'old_shelfmarks', 'notes')
    readonly_fields = ('old_shelfmarks', 'created', 'last_modified',)
    list_filter = (
        'collection',
        ('multifragment', admin.BooleanFieldListFilter),
        ('url', admin.BooleanFieldListFilter),
    )
    list_editable = ('url',)
    fields = (
        ('shelfmark', 'old_shelfmarks'),
        'collection',
        ('url', 'iiif_url'),
        'multifragment',
        'notes',
        ('created', 'last_modified')
    )
