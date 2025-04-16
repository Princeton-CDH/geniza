from modeltranslation.translator import TranslationOptions, register

from geniza.corpus.models import Document, DocumentType, Provenance


@register(Document)
class DocumentTranslationOption(TranslationOptions):
    fields = ("description",)
    required_languages = ()


@register(DocumentType)
class DocumentTypeTranslationOption(TranslationOptions):
    fields = ("name", "display_label")
    required_languages = {"en": ("name",)}
    empty_values = {"name": None}


@register(Provenance)
class ProvenanceTranslationOption(TranslationOptions):
    fields = ("name",)
    required_languages = {"en": ("name",)}
