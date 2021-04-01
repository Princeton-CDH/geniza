from django.contrib import admin

from geniza.people.models import Person
from modeltranslation.admin import TabbedTranslationAdmin

@admin.register(Person)
class PersonAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    list_display = ('sort_name',)
    search_fields = ('sort_name',)
