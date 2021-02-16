from django.contrib import admin

from geniza.corpus.models import Fragment, Collection, LanguageScript, Document, DocumentType


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('abbrev', 'library', 'location', 'collection')
    search_fields = ('library', 'location', 'collection')


@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = ('language', 'script', 'display_name')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'shelfmark', 'description', 'doctype',
        'tag_list', 'all_languages', 'is_textblock',
        'last_modified'
    )
    readonly_fields = ('old_input_by', 'old_input_date',
                       'created', 'last_modified')

    def all_languages(self, doc):
        return ','.join([str(lang) for lang in doc.languages.all()])

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .prefetch_related('tags', 'languages', 'fragments')

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())
    tag_list.short_description = 'tags'


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
