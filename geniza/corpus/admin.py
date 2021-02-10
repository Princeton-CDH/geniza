from django.contrib import admin

from geniza.corpus.models import Library, LanguageScript


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbrev')

@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = ('language', 'script', 'display_name')
