from django.contrib import admin

from geniza.corpus.models import Collection, LanguageScript, Document, DocumentType


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('abbrev', 'library', 'location', 'collection')
    search_fields = ('library', 'location', 'collection')


@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = ('language', 'script', 'display_name')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('shelfmark', 'library', # todo: fragment_historical
        'doctype', 'tag_list', 'all_languages', 'description', # todo: editor, translator
        # todo: thumbnail
        # todo: is_multifragment, has_textblock (place method on model)
        # asking: legacy data, 'fragment__side'
        'updated_at'
    )
    readonly_fields = ('old_input_by', 'old_input_date')

    def all_languages(self, doc):
        return ','.join([str(lang) for lang in doc.languages.all()])

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tags')

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)