from django.contrib.admin import register
from modeltranslation.admin import TabbedTranslationAdmin

from .models import Person, Profession


@register(Person)
class PersonAdmin(TabbedTranslationAdmin):
    autocomplete_fields = ("profession",)


@register(Profession)
class ProfessionAdmin(TabbedTranslationAdmin):
    search_fields = ("title", "description")
    list_display = ("title", "description")
