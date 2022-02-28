from modeltranslation.translator import TranslationOptions, register

from geniza.corpus.models import Document, DocumentType


@register(Document)
class DocumentTranslationOption(TranslationOptions):
    fields = ("description",)
    required_languages = ()


@register(DocumentType)
class DocumentTypeTranslationOption(TranslationOptions):
    fields = ("name", "display_label")
    required_languages = {"en": ("name",)}
    empty_values = {"name": None}
