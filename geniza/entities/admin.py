from adminsortable2.admin import SortableAdminBase
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.db.models.fields import CharField, TextField
from django.forms import ValidationError
from django.forms.widgets import Textarea, TextInput
from django.urls import reverse
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin

from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    PersonRole,
    Place,
)
from geniza.footnotes.models import Footnote


class NameInlineFormSet(BaseGenericInlineFormSet):
    """Override of the Name inline formset to require exactly one primary name."""

    DISPLAY_NAME_ERROR = "This entity must have exactly one display name."

    def clean(self):
        """Execute inherited clean method, then validate to ensure exactly one primary name."""
        super().clean()
        cleaned_data = [form.cleaned_data for form in self.forms if form.is_valid()]
        if cleaned_data:
            primary_names_count = len(
                [name for name in cleaned_data if name.get("primary") == True]
            )
            if primary_names_count == 0 or primary_names_count > 1:
                raise ValidationError(self.DISPLAY_NAME_ERROR, code="invalid")


class NameInline(GenericTabularInline):
    """Name inline for the Person and Place admins"""

    model = Name
    formset = NameInlineFormSet
    autocomplete_fields = ["language"]
    fields = (
        "name",
        "primary",
        "language",
        "notes",
        "transliteration_style",
    )
    min_num = 1
    extra = 0
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }


class PersonInline(admin.TabularInline):
    """Generic inline for people related to other objects"""

    verbose_name = "Related Person"
    verbose_name_plural = "Related People"
    autocomplete_fields = ["person", "type"]
    fields = (
        "person",
        "person_link",
        "type",
        "notes",
    )
    readonly_fields = ("person_link",)
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }
    extra = 1

    def person_link(self, obj):
        """Get the link to a related person"""
        person_path = reverse("admin:entities_person_change", args=[obj.person.id])
        return format_html(f'<a href="{person_path}">{str(obj.person)}</a>')


class FootnoteInline(GenericTabularInline):
    """Footnote inline for the Person/Place admins"""

    model = Footnote
    autocomplete_fields = ["source"]
    fields = (
        "source",
        "location",
        "notes",
        "url",
    )
    extra = 1
    formfield_overrides = {
        CharField: {"widget": TextInput(attrs={"size": "10"})},
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }
    # enable link from inline to edit footnote
    show_change_link = True


class DocumentInline(admin.TabularInline):
    """Generic related documents inline"""

    verbose_name = "Related Document"
    verbose_name_plural = "Related Documents"
    autocomplete_fields = ["type"]
    fields = (
        "document_link",
        "document_description",
        "type",
        "notes",
    )
    readonly_fields = ("document_link", "document_description")
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }
    extra = 1

    def document_link(self, obj):
        document_path = reverse("admin:corpus_document_change", args=[obj.document.id])
        return format_html(f'<a href="{document_path}">{str(obj.document)}</a>')

    document_link.short_description = "Document"

    def document_description(self, obj):
        return obj.document.description


class PersonDocumentInline(DocumentInline):
    """Related documents inline for the Person admin"""

    model = PersonDocumentRelation


class PlaceInline(admin.TabularInline):
    """Generic inline for places related to other objects"""

    verbose_name = "Related Place"
    verbose_name_plural = "Related Places"
    autocomplete_fields = ["place", "type"]
    fields = (
        "place",
        "place_link",
        "type",
        "notes",
    )
    readonly_fields = ("place_link",)
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }
    extra = 1

    def place_link(self, obj):
        """Get the link to a related place"""
        place_path = reverse("admin:entities_place_change", args=[obj.place.id])
        return format_html(f'<a href="{place_path}">{str(obj.place)}</a>')


class PersonPlaceInline(PlaceInline):
    """Inline for places related to people"""

    model = PersonPlaceRelation


class PersonPersonInline(admin.TabularInline):
    """Person-Person relationships inline for the Person admin"""

    model = PersonPersonRelation
    verbose_name = "Related Person"
    verbose_name_plural = "Related People"
    autocomplete_fields = ["to_person", "type"]
    fields = (
        "to_person",
        "person_link",
        "type",
        "notes",
    )
    fk_name = "from_person"
    readonly_fields = ("person_link",)
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }
    extra = 1

    def person_link(self, obj):
        """Get the link to a related person"""
        person_path = reverse("admin:entities_person_change", args=[obj.to_person.id])
        return format_html(f'<a href="{person_path}">{str(obj.to_person)}</a>')


@admin.register(Person)
class PersonAdmin(TabbedTranslationAdmin, SortableAdminBase, admin.ModelAdmin):
    """Admin for Person entities in the PGP"""

    search_fields = ("names__name",)
    fields = ("gender", "role", "has_page", "description")
    inlines = (
        NameInline,
        FootnoteInline,
        PersonDocumentInline,
        PersonPersonInline,
        PersonPlaceInline,
    )
    # mixed fieldsets and inlines: /admin/corpus/document/snippets/mixed_inlines_fieldsets.html
    fieldsets_and_inlines_order = (
        "i",  # NameInline
        "f",  # all Person fields
        "i",  # PersonDocumentInline
        "i",  # PersonPersonInline
        "i",  # PersonPlaceInline
    )
    own_pk = None

    def get_form(self, request, obj=None, **kwargs):
        """For Person-Person autocomplete on the PersonAdmin form, keep track of own pk"""
        if obj:
            self.own_pk = obj.pk
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """For autocomplete ONLY, remove self from queryset, so that Person-Person autocomplete
        does not include self in the list of options"""
        qs = super().get_queryset(request)
        if self.own_pk and request and request.path == "/admin/autocomplete/":
            # exclude self from queryset
            return qs.exclude(pk=int(self.own_pk))
        # otherwise, return normal queryset
        return qs


@admin.register(PersonRole)
class RoleAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of people's roles"""

    fields = ("name", "display_label")
    search_fields = ("name", "display_label")
    ordering = ("display_label", "name")


@admin.register(PersonDocumentRelationType)
class PersonDocumentRelationTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of people's relationships to documents"""

    fields = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(PersonPersonRelationType)
class PersonPersonRelationTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of people's relationships to other people"""

    fields = ("name", "category")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(PersonPlaceRelationType)
class PersonPlaceRelationTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of people's relationships to places"""

    fields = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(DocumentPlaceRelationType)
class DocumentPlaceRelationTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of documents' relationships to places"""

    fields = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


class DocumentPlaceInline(DocumentInline):
    """Related documents inline for the Person admin"""

    model = DocumentPlaceRelation


class PlacePersonInline(PersonInline):
    """Inline for people related to a place"""

    model = PersonPlaceRelation


@admin.register(Place)
class PlaceAdmin(SortableAdminBase, admin.ModelAdmin):
    """Admin for Place entities in the PGP"""

    search_fields = ("names__name",)
    fields = ("latitude", "longitude")
    inlines = (NameInline, DocumentPlaceInline, PlacePersonInline, FootnoteInline)
    fieldsets_and_inlines_order = (
        "i",  # NameInline
        "f",  # lat/long fieldset
        "i",  # DocumentPlaceInline
        "i",  # PlacePersonInline
        "i",  # FootnoteInline
    )
