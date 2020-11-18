from modeltranslation.translator import register, TranslationOptions
from .models import Person, Profession


@register(Person)
class PersonTranslationOptions(TranslationOptions):
    fields = ("name",)
    required_languages = ("en",)


@register(Profession)
class ProfessionTranslationOptions(TranslationOptions):
    fields = ("title",)
    required_languages = ("en",)
