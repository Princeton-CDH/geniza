from modeltranslation.translator import TranslationOptions, register

from geniza.entities.models import (
    DocumentPlaceRelationType,
    Person,
    PersonDocumentRelationType,
    PersonPersonRelationType,
    PersonPlaceRelationType,
    PersonRole,
)


@register(Person)
class PersonTranslationOption(TranslationOptions):
    fields = ("description",)
    required_languages = ()


@register(PersonDocumentRelationType)
class PersonDocumentRelationTypeOption(TranslationOptions):
    fields = ("name",)
    required_languages = ()


@register(PersonPersonRelationType)
class PersonPersonRelationTypeOption(TranslationOptions):
    fields = ("name", "converse_name")
    required_languages = ()


@register(PersonRole)
class PersonRoleTranslationOption(TranslationOptions):
    fields = ("name", "display_label")
    required_languages = {"en": ("name",)}
    empty_values = {"name": None}


@register(PersonPlaceRelationType)
class PersonPlaceRelationTypeOption(TranslationOptions):
    fields = ("name",)
    required_languages = ()


@register(DocumentPlaceRelationType)
class DocumentPlaceRelationTypeOption(TranslationOptions):
    fields = ("name",)
    required_languages = ()
