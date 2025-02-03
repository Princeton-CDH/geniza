from modeltranslation.translator import TranslationOptions, register

from geniza.entities.models import (
    DocumentPlaceRelationType,
    Event,
    Person,
    PersonDocumentRelationType,
    PersonPersonRelationType,
    PersonPlaceRelationType,
    PersonRole,
    PlacePlaceRelationType,
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


@register(PlacePlaceRelationType)
class PlacePlaceRelationTypeOption(TranslationOptions):
    fields = ("name", "converse_name")
    required_languages = ()


@register(Event)
class EventOption(TranslationOptions):
    fields = ("name", "description")
    required_languages = ()
