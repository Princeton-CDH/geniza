from modeltranslation.translator import TranslationOptions, register

from geniza.footnotes.models import Creator, Source


@register(Source)
class SourceTranslationOption(TranslationOptions):
    fields = ("title",)
    required_languages = ()


@register(Creator)
class CreatorTranslationOption(TranslationOptions):
    fields = ("first_name", "last_name")
    required_languages = ("en",)
