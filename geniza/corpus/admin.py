from django.contrib import admin

from geniza.corpus.models import Collection, LanguageScript


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('abbrev', 'library', 'location', 'collection')
    search_fields = ('library', 'location', 'collection')


@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = ('language', 'script', 'display_name')
