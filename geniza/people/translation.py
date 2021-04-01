from modeltranslation.translator import register, TranslationOptions
from .models import Person

@register(Person)
class PersonTranslationOption(TranslationOptions):
    fields = ("sort_name",)
    required_languages = ("en",)