from adminsortable2.admin import SortableAdminBase
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.db.models.fields import CharField, TextField
from django.forms.widgets import Textarea, TextInput
from django.urls import reverse
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin

from geniza.entities.models import (
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonRole,
)
from geniza.footnotes.models import Footnote


class PersonNameInline(GenericTabularInline):
    """Name inline for the Person admin"""

    model = Name
    autocomplete_fields = ["language"]
    fields = (
        "name",
        "primary",
        "language",
        "notes",
    )
    min_num = 1
    extra = 0
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }


class PersonFootnoteInline(GenericTabularInline):
    """Footnote inline for the Person admin"""

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


class PersonDocumentInline(admin.TabularInline):
    """Related documents inline for the Person admin"""

    model = PersonDocumentRelation
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
        PersonNameInline,
        PersonFootnoteInline,
        PersonDocumentInline,
        PersonPersonInline,
    )
    # mixed fieldsets and inlines: /admin/corpus/document/snippets/mixed_inlines_fieldsets.html
    fieldsets_and_inlines_order = ("i", "f", "i", "i", "i")
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


@admin.register(PersonDocumentRelationType)
class PersonDocumentRelationTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of people's relationships to documents"""

    fields = ("name",)
    search_fields = ("name",)


@admin.register(PersonPersonRelationType)
class PersonPersonRelationTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of people's relationships to other people"""

    fields = ("name", "category")
    search_fields = ("name",)
