from modeltranslation.translator import register, TranslationOptions

from geniza.footnotes.models import Source, Creator


@register(Source)
class SourceTranslationOption(TranslationOptions):
    fields = ("title",)
    required_languages = ()


@register(Creator)
class CreatorTranslationOption(TranslationOptions):
    fields = ("first_name", "last_name")
    required_languages = ("en",)
