from modeltranslation.translator import register, TranslationOptions
from .models import Person, Profession


@register(Person)
class PersonTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Profession)
class ProfessionTranslationOptions(TranslationOptions):
    fields = ("title",)
