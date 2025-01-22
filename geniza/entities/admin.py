from itertools import groupby

from adminsortable2.admin import SortableAdminBase
from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models.fields import CharField, TextField
from django.forms import ModelChoiceField, ValidationError
from django.forms.models import ModelChoiceIterator
from django.forms.widgets import Textarea, TextInput
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from modeltranslation.admin import TabbedTranslationAdmin

from geniza.common.admin import TypedRelationInline
from geniza.corpus.dates import standard_date_display
from geniza.corpus.models import DocumentEventRelation
from geniza.entities.forms import (
    EventForm,
    EventPersonForm,
    EventPlaceForm,
    PersonPersonForm,
    PersonPlaceForm,
    PlacePersonForm,
    PlacePlaceForm,
)
from geniza.entities.metadata_export import (
    AdminPersonExporter,
    AdminPlaceExporter,
    PersonRelationsExporter,
    PlaceRelationsExporter,
)
from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Event,
    Name,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    PersonEventRelation,
    PersonPersonRelation,
    PersonPersonRelationType,
    PersonPlaceRelation,
    PersonPlaceRelationType,
    PersonRole,
    Place,
    PlaceEventRelation,
    PlacePlaceRelation,
    PlacePlaceRelationType,
)
from geniza.entities.views import (
    PersonDocumentRelationTypeMerge,
    PersonMerge,
    PersonPersonRelationTypeMerge,
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

    def get_formset(self, request, obj=None, **kwargs):
        """Override in order to remove the delete button from the language field"""
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields["language"].widget.can_delete_related = False
        return formset


class PersonInline(admin.TabularInline):
    """Generic inline for people related to other objects"""

    verbose_name = "Related Person"
    verbose_name_plural = "Related People"
    extra = 1


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
    autocomplete_fields = ("document", "type")
    fields = (
        "document",
        "dating_range",
        "document_description",
        "type",
        "notes",
    )
    readonly_fields = ("document_description", "dating_range")
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }
    extra = 1

    def document_description(self, obj):
        return obj.document.description

    def dating_range(self, obj):
        """Show the range of dates associated with the document (inferred and document)
        on the admin inline to show the sources of automatic dating"""
        dating_range = [d.isoformat() for d in obj.document.dating_range() if d]
        return standard_date_display("/".join(dating_range)) or "-"


class PersonDocumentInline(TypedRelationInline, DocumentInline):
    """Related documents inline for the Person admin"""

    model = PersonDocumentRelation


class PlaceInline(admin.TabularInline):
    """Generic inline for places related to other objects"""

    verbose_name = "Related Place"
    verbose_name_plural = "Related Places"
    extra = 1


class PersonPlaceInline(TypedRelationInline, PlaceInline):
    """Inline for places related to people"""

    model = PersonPlaceRelation
    form = PersonPlaceForm


class PersonPersonRelationTypeChoiceIterator(ModelChoiceIterator):
    """Override ModelChoiceIterator in order to group Person-Person
    relationship types by category"""

    def __iter__(self):
        """Override the iterator to group type by category"""
        # first, display empty label if applicable
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        # then group the queryset (ordered by category, then name) by category
        groups = groupby(
            self.queryset.order_by("category", "name"), key=lambda x: x.category
        )
        # map category keys to their full names for display
        category_names = dict(PersonPersonRelationType.CATEGORY_CHOICES)
        # return the groups in the format expected by ModelChoiceField
        for category, types in groups:
            yield (category_names[category], [(type.id, type.name) for type in types])


class PersonPersonRelationTypeChoiceField(ModelChoiceField):
    """Override ModelChoiceField's iterator property to use our ModelChoiceIterator
    override"""

    iterator = PersonPersonRelationTypeChoiceIterator


class PersonPersonInline(admin.TabularInline):
    """Person-Person relationships inline for the Person admin"""

    model = PersonPersonRelation
    verbose_name = "Related Person"
    verbose_name_plural = "Related People (input manually)"
    form = PersonPersonForm
    fk_name = "from_person"
    extra = 1

    def get_formset(self, request, obj=None, **kwargs):
        """Override 'type' field for PersonPersonRelation, change ModelChoiceField
        to our new PersonPersonRelationTypeChoiceField"""
        formset = super().get_formset(request, obj=None, **kwargs)
        formset.form.base_fields["type"] = PersonPersonRelationTypeChoiceField(
            queryset=PersonPersonRelationType.objects.all()
        )
        return formset


class PersonPersonReverseInline(admin.TabularInline):
    """Person-Person reverse relationships inline for the Person admin"""

    model = PersonPersonRelation
    verbose_name = "Related Person"
    verbose_name_plural = "Related People (automatically populated)"
    fields = (
        "from_person",
        "relation",
        "notes",
    )
    fk_name = "to_person"
    readonly_fields = ("from_person", "relation", "notes")
    extra = 0
    max_num = 0

    def relation(self, obj=None):
        """Get the relationship type's converse name, if it exists, or else the type name"""
        return (obj.type.converse_name or str(obj.type)) if obj else None


class PersonEventInline(admin.TabularInline):
    """Inline for events related to a person"""

    autocomplete_fields = ("event",)
    fields = ("event", "notes")
    model = PersonEventRelation
    min_num = 0
    extra = 1
    show_change_link = True
    verbose_name = "Related Event"
    verbose_name_plural = "Related Events"
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": "4"})},
    }


@admin.register(Person)
class PersonAdmin(TabbedTranslationAdmin, SortableAdminBase, admin.ModelAdmin):
    """Admin for Person entities in the PGP"""

    search_fields = ("name_unaccented", "names__name")
    fields = (
        "slug",
        "gender",
        "role",
        "has_page",
        "date",
        "automatic_date",
        "description",
    )
    readonly_fields = ("automatic_date",)
    inlines = (
        NameInline,
        FootnoteInline,
        PersonDocumentInline,
        PersonPersonInline,
        PersonPersonReverseInline,
        PersonPlaceInline,
        PersonEventInline,
    )
    # mixed fieldsets and inlines: /templates/admin/snippets/mixed_inlines_fieldsets.html
    fieldsets_and_inlines_order = (
        "i",  # NameInline
        "f",  # all Person fields
        "i",  # PersonDocumentInline
        "i",  # PersonPersonInline
        "i",  # PersonPersonReverseInline
        "i",  # PersonPlaceInline
        "i",  # PersonEventInline
    )
    own_pk = None

    def save_related(self, request, form, formsets, change):
        """Override save to ensure slug is generated if empty. Adapted from mep-django"""
        super().save_related(request, form, formsets, change)

        # this must be done after related objects are saved, because generate_slug
        # requires related Name records
        person = form.instance
        if not person.slug:
            person.generate_slug()
            person.save()

    def get_form(self, request, obj=None, **kwargs):
        """For Person-Person autocomplete on the PersonAdmin form, keep track of own pk"""
        if obj:
            self.own_pk = obj.pk
        else:
            # reset own_pk to None if we are creating a new person
            self.own_pk = None
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """For autocomplete ONLY, remove self from queryset, so that Person-Person autocomplete
        does not include self in the list of options"""
        # also add unaccented name to queryset so we can search on it
        qs = (
            super()
            .get_queryset(request)
            .annotate(
                # ArrayAgg to group together related values from related model instances
                name_unaccented=ArrayAgg("names__name__unaccent", distinct=True),
            )
        )

        # only modify if this is the person-person autocomplete request
        is_autocomplete = request and request.path == "/admin/autocomplete/"
        is_personperson = (
            request
            and request.GET
            and request.GET.get("model_name") == "personpersonrelation"
        )
        if self.own_pk and is_autocomplete and is_personperson:
            # exclude self from queryset
            return qs.exclude(pk=int(self.own_pk))
        # otherwise, return normal queryset
        return qs

    @admin.display(description="Merge selected people")
    def merge_people(self, request, queryset=None):
        """Admin action to merge selected people. This action redirects to an intermediate
        page, which displays a form to review for confirmation and choose the primary person before merging.
        """
        # Functionality almost identical to Document merge

        # NOTE: using selected ids from form and ignoring queryset
        # because we can't pass the queryset via redirect
        selected = request.POST.getlist("_selected_action")
        if len(selected) < 2:
            messages.error(request, "You must select at least two people to merge")
            return HttpResponseRedirect(reverse("admin:entities_person_changelist"))
        return HttpResponseRedirect(
            "%s?ids=%s" % (reverse("admin:person-merge"), ",".join(selected)),
            status=303,
        )  # status code 303 means "See Other"

    @admin.display(description="Export selected people to CSV")
    def export_to_csv(self, request, queryset=None):
        """Stream tabular data as a CSV file"""
        queryset = queryset or self.get_queryset(request)
        exporter = AdminPersonExporter(queryset=queryset, progress=False)
        return exporter.http_export_data_csv()

    def export_relations_to_csv(self, request, pk):
        """Stream related objects data for a single object instance as a CSV file"""
        queryset = Person.objects.filter(pk=pk)
        exporter = PersonRelationsExporter(queryset=queryset, progress=False)
        return exporter.http_export_data_csv()

    def get_urls(self):
        """Return admin urls; adds custom URLs for exporting as CSV, merging people"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="person-csv",
            ),
            path(
                "<int:pk>/relations-csv/",
                self.admin_site.admin_view(self.export_relations_to_csv),
                name="person-relations-csv",
            ),
            path(
                "merge/",
                PersonMerge.as_view(),
                name="person-merge",
            ),
        ]
        return urls + super().get_urls()

    def automatic_date(self, obj):
        """Display automatically generated date/date range for an event as a formatted string"""
        return standard_date_display(obj.documents_date_range)

    actions = (export_to_csv, merge_people)


@admin.register(PersonRole)
class RoleAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of people's roles"""

    fields = ("name", "display_label")
    search_fields = ("name", "display_label")
    ordering = ("display_label", "name")


class RelationTypeMergeAdminMixin:
    @admin.display(description="Merge selected %(verbose_name_plural)s")
    def merge_relation_types(self, request, queryset=None):
        """Admin action to merge selected entity-entity relation types. This
        action redirects to an intermediate page, which displays a form to
        review for confirmation and choose the primary type before merging.
        """
        selected = request.POST.getlist("_selected_action")
        if len(selected) < 2:
            messages.error(
                request,
                "You must select at least two person-person relationships to merge",
            )
            return HttpResponseRedirect(
                reverse("admin:entities_%s_changelist" % self.model._meta.model_name)
            )
        return HttpResponseRedirect(
            "%s?ids=%s"
            % (
                reverse(f"admin:{self.merge_path_name}"),
                ",".join(selected),
            ),
            status=303,
        )  # status code 303 means "See Other"

    def get_urls(self):
        """Return admin urls; adds custom URL for merging"""
        urls = [
            path(
                "merge/",
                self.view_class.as_view(),
                name=self.merge_path_name,
            ),
        ]
        return urls + super().get_urls()

    actions = (merge_relation_types,)


@admin.register(PersonDocumentRelationType)
class PersonDocumentRelationTypeAdmin(
    RelationTypeMergeAdminMixin, TabbedTranslationAdmin, admin.ModelAdmin
):
    """Admin for managing the controlled vocabulary of people's relationships to documents"""

    fields = ("name",)
    search_fields = ("name",)
    ordering = ("name",)
    merge_path_name = "person-document-relation-type-merge"
    view_class = PersonDocumentRelationTypeMerge


@admin.register(PersonPersonRelationType)
class PersonPersonRelationTypeAdmin(
    RelationTypeMergeAdminMixin, TabbedTranslationAdmin, admin.ModelAdmin
):
    """Admin for managing the controlled vocabulary of people's relationships to other people"""

    fields = ("name", "converse_name", "category")
    search_fields = ("name",)
    ordering = ("name",)
    merge_path_name = "person-person-relation-type-merge"
    view_class = PersonPersonRelationTypeMerge


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


class DocumentPlaceInline(TypedRelationInline, DocumentInline):
    """Related documents inline for the Person admin"""

    model = DocumentPlaceRelation


class PlacePersonInline(TypedRelationInline, PersonInline):
    """Inline for people related to a place"""

    model = PersonPlaceRelation
    form = PlacePersonForm


class PlacePlaceInline(TypedRelationInline, admin.TabularInline):
    """Place-Place relationships inline for the Place admin"""

    model = PlacePlaceRelation
    verbose_name = "Related Place"
    verbose_name_plural = "Related Places (input manually)"
    form = PlacePlaceForm
    fk_name = "place_a"
    extra = 1


class PlacePlaceReverseInline(admin.TabularInline):
    """Place-Place reverse relationships inline for the Place admin"""

    model = PlacePlaceRelation
    verbose_name = "Related Place"
    verbose_name_plural = "Related Places (automatically populated)"
    fields = (
        "place_a",
        "type",
        "notes",
    )
    fk_name = "place_b"
    readonly_fields = ("place_a", "type", "notes")
    extra = 0
    max_num = 0


class PlaceEventInline(admin.TabularInline):
    """Inline for events related to a place"""

    autocomplete_fields = ("event",)
    fields = ("event", "notes")
    model = PlaceEventRelation
    min_num = 0
    extra = 1
    show_change_link = True
    verbose_name = "Related Event"
    verbose_name_plural = "Related Events"
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": "4"})},
    }

    def get_formset(self, request, obj=None, **kwargs):
        """Disable the 'add' link for an Event from a Place. Must be added from
        a document or created manually with a document attached in the admin."""
        formset = super().get_formset(request, obj, **kwargs)
        service = formset.form.base_fields["event"]
        service.widget.can_add_related = False
        return formset


@admin.register(Place)
class PlaceAdmin(SortableAdminBase, admin.ModelAdmin):
    """Admin for Place entities in the PGP"""

    search_fields = ("name_unaccented", "names__name")
    fields = ("slug", ("latitude", "longitude"), "notes")
    inlines = (
        NameInline,
        DocumentPlaceInline,
        PlacePersonInline,
        PlacePlaceInline,
        PlacePlaceReverseInline,
        PlaceEventInline,
        FootnoteInline,
    )
    fieldsets_and_inlines_order = (
        "i",  # NameInline
        "f",  # lat/long fieldset
        "i",  # DocumentPlaceInline
        "i",  # PlacePersonInline
        "i",  # PlacePlaceInline
        "i",  # PlacePlaceReverseInline
        "i",  # PlaceEventInline
        "i",  # FootnoteInline
    )

    def save_related(self, request, form, formsets, change):
        """Override save to ensure slug is generated if empty. Adapted from mep-django"""
        super().save_related(request, form, formsets, change)

        # this must be done after related objects are saved, because generate_slug
        # requires related Name records
        place = form.instance
        if not place.slug:
            place.generate_slug()
            place.save()

    def get_queryset(self, request):
        """Modify queryset to add unaccented name annotation field, so that places
        can be searched from admin list view without entering diacritics"""
        return (
            super()
            .get_queryset(request)
            .annotate(
                # ArrayAgg to group together related values from related model instances
                name_unaccented=ArrayAgg("names__name__unaccent", distinct=True),
            )
        )

    @admin.display(description="Export selected places to CSV")
    def export_to_csv(self, request, queryset=None):
        """Stream tabular data as a CSV file"""
        queryset = queryset or self.get_queryset(request)
        exporter = AdminPlaceExporter(queryset=queryset, progress=False)
        return exporter.http_export_data_csv()

    def export_relations_to_csv(self, request, pk):
        """Stream related objects data for a single object instance as a CSV file"""
        queryset = Place.objects.filter(pk=pk)
        exporter = PlaceRelationsExporter(queryset=queryset, progress=False)
        return exporter.http_export_data_csv()

    def get_urls(self):
        """Return admin urls; adds custom URL for exporting as CSV"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="place-csv",
            ),
            path(
                "<int:pk>/relations-csv/",
                self.admin_site.admin_view(self.export_relations_to_csv),
                name="place-relations-csv",
            ),
        ]
        return urls + super().get_urls()

    actions = (export_to_csv,)


@admin.register(PlacePlaceRelationType)
class PlacePlaceRelationTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of places' relationships to other places"""

    fields = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


class EventDocumentInline(DocumentInline):
    """Related documents inline for the Event admin"""

    model = DocumentEventRelation
    autocomplete_fields = ("document",)
    fields = (
        "document",
        "document_description",
        "notes",
    )
    extra = 0

    def get_min_num(self, request, obj=None, **kwargs):
        """On new Event creation, set min_num of Document relationships conditionally based on
        whether it is being created from a popup in the admin edit page for a Document, or
        created from the Event admin"""
        from_document = (
            "from_document" in request.GET and request.GET["from_document"] == "true"
        )
        if from_document and obj is None:
            # For admin convenience: If a new Event is being created (via popup) in the Document
            # admin, min number of associated documents should be 0; otherwise admins would have
            # to create the relationship manually from within the popup even though it is about
            # to be created by saving the Document.
            # NOTE: If an Event is created in the Document admin and the Document is NOT saved,
            # or the relationship is removed before saving, an orphan Event could be created.
            return 0
        else:
            # If accessed via Event section of admin, or a popup from other related objects like
            # Person, requires minimum 1 related Document.
            return 1


class EventPersonInline(PersonInline):
    """Related people inline for the Event admin"""

    model = PersonEventRelation
    form = EventPersonForm
    autocomplete_fields = ("person",)
    fields = ("person", "notes")


class EventPlaceInline(PlaceInline):
    """Related places inline for the Event admin"""

    model = PlaceEventRelation
    form = EventPlaceForm
    autocomplete_fields = ("place",)
    fields = ("place", "notes")


@admin.register(Event)
class EventAdmin(TabbedTranslationAdmin, SortableAdminBase, admin.ModelAdmin):
    """Admin for Event entities in the PGP"""

    fields = ("name", "description", "standard_date", "display_date", "automatic_date")
    readonly_fields = ("automatic_date",)
    search_fields = ("name",)
    ordering = ("name",)
    inlines = (EventDocumentInline, EventPersonInline, EventPlaceInline, FootnoteInline)
    form = EventForm

    def automatic_date(self, obj):
        """Display automatically generated date/date range for an event as a formatted string"""
        return standard_date_display(obj.documents_date_range)
