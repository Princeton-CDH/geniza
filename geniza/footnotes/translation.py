from modeltranslation.translator import register, TranslationOptions
from .models import Source

@register(Source)
class SourceTranslationOption(TranslationOptions):
    fields = ("title",)
    required_languages = ("en",)