from modeltranslation.translator import TranslationOptions, register

from geniza.pages.models import Contributor


@register(Contributor)
class CreatorTranslationOption(TranslationOptions):
    fields = ("first_name", "last_name", "role")
    required_languages = ("en",)
