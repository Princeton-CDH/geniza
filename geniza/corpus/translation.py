from modeltranslation.translator import TranslationOptions, register

from geniza.corpus.models import Document


@register(Document)
class DocumentTranslationOption(TranslationOptions):
    fields = ("description",)
    required_languages = ()
