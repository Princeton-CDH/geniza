from django.contrib import admin

from geniza.corpus.models import Library


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbrev')
