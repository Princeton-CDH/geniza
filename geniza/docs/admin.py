from django.contrib import admin

from geniza.docs.models import Library


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbrev')
