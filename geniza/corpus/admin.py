from django.contrib import admin
from django.db.models import Count

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
    list_display = ('language', 'script', 'display_name', 'documents',
                    'probable_documents')

    document_admin_url = 'admin:corpus_document_changelist'

    class Media:
        css = {
            'all': ('css/admin-local.css', )
        }

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .annotate(Count('document', distinct=True),
                      Count('probable_document', distinct=True))

    def documents(self, obj):
        return format_html(
            '<a href="{0}?languages__id__exact={1!s}">{2}</a>',
            reverse(self.document_admin_url), str(obj.id),
            obj.document__count
        )
    documents.short_description = "# documents on which this language appears"
    documents.admin_order_field = 'document__count'

    def probable_documents(self, obj):
        return format_html(
            '<a href="{0}?probable_languages__id__exact={1!s}">{2}</a>',
            reverse(self.document_admin_url), str(obj.id),
            obj.probable_document__count
        )
    probable_documents.short_description = \
        "# documents on which this language might appear (requires confirmation)"
    probable_documents.admin_order_field = 'probable_document__count'


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
                       'created', 'last_modified', 'shelfmark', 'id')
    search_fields = ('fragments__shelfmark', 'tags__name', 'description',
                     'old_input_by')
    # TODO include search on edition once we add footnotes

    list_filter = (
        'doctype', 'languages', 'textblock__extent_label',
        'probable_languages',
    )

    fields = (
        ('shelfmark', 'id'),
        'doctype',
        'languages',
        'probable_languages',
        'language_note',
        'description',
        'tags',
        # edition, translation
        'notes',
        # text block
        ('old_input_by', 'old_input_date'),
        ('created', 'last_modified')
    )
    filter_horizontal = ('languages', 'probable_languages')
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
