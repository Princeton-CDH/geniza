from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from dal import autocomplete
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import unquote
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import CharField, Count, F, Q, TextField
from django.db.models.functions import Concat
from django.forms.widgets import HiddenInput, Textarea, TextInput
from django.http import HttpResponseRedirect
from django.urls import path, resolve, reverse
from django.utils import timezone
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin

from geniza.annotations.models import Annotation
from geniza.common.admin import TypedRelationInline, custom_empty_field_list_filter
from geniza.corpus.dates import DocumentDateMixin, standard_date_display
from geniza.corpus.forms import (
    DocumentEventWidgetWrapper,
    DocumentPersonForm,
    DocumentPlaceForm,
)
from geniza.corpus.metadata_export import AdminDocumentExporter, AdminFragmentExporter
from geniza.corpus.models import (
    Collection,
    Dating,
    Document,
    DocumentEventRelation,
    DocumentType,
    Fragment,
    LanguageScript,
    MaterialSupport,
    Provenance,
    TextBlock,
)
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.views import DocumentMerge
from geniza.entities.admin import PersonInline, PlaceInline
from geniza.entities.models import DocumentPlaceRelation, PersonDocumentRelation
from geniza.footnotes.admin import DocumentFootnoteInline
from geniza.footnotes.models import Footnote


class FragmentTextBlockInline(admin.TabularInline):
    """The TextBlockInline class for the Fragment admin"""

    model = TextBlock
    fields = (
        "document_link",
        "document_description",
        "multifragment",
        "side",
        "region",
    )
    readonly_fields = ("document_link", "document_description", "side")
    extra = 1

    def document_link(self, obj):
        document_path = reverse("admin:corpus_document_change", args=[obj.document.id])
        return format_html(f'<a href="{document_path}">{str(obj.document)}</a>')

    document_link.short_description = "Document"

    def document_description(self, obj):
        return obj.document.description


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("library", "name", "lib_abbrev", "abbrev", "location")
    search_fields = ("library", "location", "name")
    list_display_links = ("library", "name")
    fields = ("library", "lib_abbrev", "name", "abbrev", "location")


@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = (
        "language",
        "script",
        "display_name",
        "documents",
        "secondary_documents",
    )

    document_admin_url = "admin:corpus_document_changelist"
    search_fields = ("language", "display_name")

    class Media:
        css = {"all": ("css/admin-local.css",)}

    def get_queryset(self, request):
        # The annotations we use for document count on the list view
        # make the search too slow for autocomplete.
        # Reset to original, unannotated queryset *only* for autocomplete
        qs = super().get_queryset(request)
        if request and request.path == "/admin/autocomplete/":
            # return without annotations
            return qs
        # otherwise, annotate with counts
        return qs.annotate(
            Count("document", distinct=True),
            Count("secondary_document", distinct=True),
        )

    @admin.display(
        ordering="document__count",
        description="# documents where this is the primary language",
    )
    def documents(self, obj):
        return format_html(
            '<a href="{0}?languages__id__exact={1!s}">{2}</a>',
            reverse(self.document_admin_url),
            str(obj.id),
            obj.document__count,
        )

    @admin.display(
        ordering="secondary_document__count",
        description="# documents where this is a secondary language",
    )
    def secondary_documents(self, obj):
        return format_html(
            '<a href="{0}?secondary_languages__id__exact={1!s}">{2}</a>',
            reverse(self.document_admin_url),
            str(obj.id),
            obj.secondary_document__count,
        )


class DocumentTextBlockInline(SortableInlineAdminMixin, admin.TabularInline):
    """The TextBlockInline class for the Document admin"""

    model = TextBlock
    autocomplete_fields = ["fragment"]
    readonly_fields = (
        "thumbnail",
        "side",
        "fragment_provenance_display",
        "fragment_material_support",
        "fragment_provenance",
    )
    fields = (
        "fragment",
        "multifragment",
        "side",
        "region",
        "order",
        "certain",
        "fragment_provenance_display",
        "fragment_material_support",
        "fragment_provenance",
        "thumbnail",
        "selected_images",
    )
    min_num = 1
    extra = 0
    formfield_overrides = {
        CharField: {"widget": TextInput(attrs={"size": "10"})},
        ArrayField: {"widget": HiddenInput()},  # hidden input for selected_images
    }

    @admin.display(description="Provenance")
    def fragment_provenance_display(self, obj):
        return str(obj.fragment.provenance_display or "")

    @admin.display(description="Provenance notes")
    def fragment_provenance(self, obj):
        return obj.fragment.provenance

    @admin.display(description="MaterialSupport")
    def fragment_material_support(self, obj):
        return str(obj.fragment.material_support or "")


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        exclude = ()
        widgets = {
            "language_note": Textarea(attrs={"rows": 1}),
            "needs_review": Textarea(attrs={"rows": 3}),
            "notes": Textarea(attrs={"rows": 3}),
            "image_overrides": HiddenInput(),
            "tags": autocomplete.TaggitSelect2("tag-autocomplete"),
        }

    def clean(self):
        # error if there is any overlap between language and secondary lang
        secondary_languages = self.cleaned_data["secondary_languages"]
        if any(
            slang in self.cleaned_data["languages"] for slang in secondary_languages
        ):
            raise ValidationError(
                "The same language cannot be both primary and secondary."
            )


class HasTranscriptionListFilter(admin.SimpleListFilter):
    """Custom list filter for documents with associated transcription content"""

    title = "Transcription"
    parameter_name = "transcription"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has transcription"),
            ("no", "No transcription"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                footnotes__doc_relation__contains=Footnote.DIGITAL_EDITION
            )
        if self.value() == "no":
            return queryset.exclude(
                footnotes__doc_relation__contains=Footnote.DIGITAL_EDITION
            )


class HasTranslationListFilter(admin.SimpleListFilter):
    """Custom list filter for documents with associated translation content"""

    title = "Translation"
    parameter_name = "translation"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has translation"),
            ("yes_en", "Has English translation"),
            ("yes_he", "Has Hebrew translation"),
            ("no", "No translation"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                footnotes__doc_relation__contains=Footnote.DIGITAL_TRANSLATION
            )
        # Filters for English and Hebrew translations:
        # In order to find documents with footnotes that satisfy both conditions, we need to make
        # a second query within the first, per Django docs ("Spanning multi-valued relationships")
        if self.value() == "yes_en":
            return queryset.filter(
                footnotes__in=Footnote.objects.filter(
                    doc_relation__contains=Footnote.DIGITAL_TRANSLATION,
                    source__languages__name="English",
                ),
            )
        if self.value() == "yes_he":
            return queryset.filter(
                footnotes__in=Footnote.objects.filter(
                    doc_relation__contains=Footnote.DIGITAL_TRANSLATION,
                    source__languages__name="Hebrew",
                ),
            )
        if self.value() == "no":
            return queryset.exclude(
                footnotes__doc_relation__contains=Footnote.DIGITAL_TRANSLATION
            )


class TextInputListFilter(admin.SimpleListFilter):
    """
    Custom list filter class for text input, adapted from this solution by Haki Benita:
    https://hakibenita.com/how-to-add-a-text-filter-to-django-admin
    """

    template = "admin/corpus/text_input_filter.html"

    def lookups(self, request, model_admin):
        # Dummy, required to show the filter.
        return ((),)

    def choices(self, changelist):
        # Grab only the "all" option.
        all_choice = next(super().choices(changelist))
        all_choice["query_parts"] = (
            (k, v)
            for k, v in changelist.get_filters_params().items()
            if k != self.parameter_name
        )
        yield all_choice


class DateListFilter(TextInputListFilter):
    """Admin date range filter for documents, using Solr queryset"""

    def queryset(self, request, queryset):
        """Get the filtered queryset based on date range filter input"""
        if self.value() is not None:
            date = self.value()

            # exclude any results that don't have a date or dating
            queryset = queryset.exclude(
                Q(dating__isnull=True) & Q(doc_date_standard="")
            )

            # get all before "to date" if we're using DateBeforeListFilter,
            # otherwise get all after "from date"
            date_filter = (
                ("[* TO %s]" % date)
                if self.parameter_name == "date__lte"
                else ("[%s TO *]" % date)
            )

            # use Solr to take advantage of processed date range fields
            sqs = DocumentSolrQuerySet()

            # different solr fields for dates, depdending on whether or not inferred are included
            date_field = (
                "document_date_dr"
                if request.GET.get("exclude_inferred", None) == "true"
                else "document_dating_dr"
            )
            date_filter_opts = {date_field: date_filter}
            sqs = sqs.filter(**date_filter_opts).only("pgpid").get_results(rows=100000)

            # filter queryset by id if there are results
            pks = [r["pgpid"] for r in sqs]
            if sqs:
                queryset = queryset.filter(pk__in=pks)
            else:
                queryset = queryset.none()
            if not (DocumentDateMixin.re_date_format.match(date)):
                messages.error(
                    request, "Dates must be in the format YYYY-MM-DD or YYYY."
                )
            return queryset


class DateAfterListFilter(DateListFilter):
    parameter_name = "date__gte"
    title = "Date from (CE)"


class DateBeforeListFilter(DateListFilter):
    parameter_name = "date__lte"
    title = "Date to (CE)"


class InferredDatingListFilter(admin.SimpleListFilter):
    """Custom list filter to indicate whether or not inferred datings should be considered, when
    filtering by date. Only applies when at least one date filter is also applied."""

    title = "date type (if at least one date filter active)"
    parameter_name = "exclude_inferred"

    def lookups(self, request, model_admin):
        return (("true", "Document dates only"),)

    def queryset(self, request, queryset):
        # no change to queryset, we only need the request param to adjust a different queryset
        return queryset

    def choices(self, changelist):
        # Modify the "All" option's display text to clarify its meaning
        choices = list(super().choices(changelist))
        choices[0]["display"] = "Document and inferred dates"
        return iter(choices)


class DocumentDatingInline(admin.TabularInline):
    """Inline for inferred dates on a document"""

    model = Dating
    fields = (
        "display_date",
        "standard_date",
        "rationale",
        "notes",
    )
    min_num = 0
    extra = 1
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4})},
    }


class DocumentPersonInline(TypedRelationInline, PersonInline):
    """Inline for people related to a document"""

    model = PersonDocumentRelation
    form = DocumentPersonForm


class DocumentPlaceInline(TypedRelationInline, PlaceInline):
    """Inline for places related to a document"""

    model = DocumentPlaceRelation
    form = DocumentPlaceForm


class DocumentEventInline(admin.TabularInline):
    """Inline for events related to a document"""

    autocomplete_fields = ("event",)
    fields = ("event", "notes")
    model = DocumentEventRelation
    min_num = 0
    extra = 1
    show_change_link = True
    verbose_name = "Related Event"
    verbose_name_plural = "Related Events"
    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": "4"})},
    }

    def get_formset(self, request, obj=None, **kwargs):
        """Override the Event related field widget, so that the new Event form can be saved
        without attaching a document in the popup."""
        formset = super().get_formset(request, obj, **kwargs)
        event_field = formset.form.base_fields["event"]
        # these args/kwargs are usually populated automatically by django's related model field
        # processing, but since we are overriding the wrapper we have to manually populate them
        event_field.widget = DocumentEventWidgetWrapper(
            autocomplete.ModelSelect2(),
            rel=DocumentEventRelation._meta.get_field("event").remote_field,
            admin_site=admin.site,
        )
        event_field.widget.can_change_related = True
        return formset


@admin.register(Document)
class DocumentAdmin(TabbedTranslationAdmin, SortableAdminBase, admin.ModelAdmin):
    form = DocumentForm
    # NOTE: columns display for default and needs review display
    # are controlled via admin css; update the css if you change the order here
    list_display = (
        "id",
        "needs_review",  # disabled by default with css
        "shelfmark_display",  #  = combined shelfmark or shelfmark override
        "description",
        "doctype",
        "all_tags",
        "all_languages",
        "last_modified",
        "has_transcription",
        "has_image",
        "is_public",
    )
    readonly_fields = (
        "created",
        "last_modified",
        "shelfmark",
        "id",
        "view_old_pgpids",
        "standard_date",
        "admin_thumbnails",
        "fragment_historical_shelfmarks",
        "cite_description",
    )
    search_fields = (
        "fragments__shelfmark",
        "id",
        "old_pgpids",
    )
    # TODO include search on edition once we add footnotes
    save_as = True
    # display unset document type as Unknown
    empty_value_display = "Unknown"

    # customize old pgpid display so unset does not show up as "Unknown"
    @admin.display(
        description="Old PGPIDs",
    )
    def view_old_pgpids(self, obj):
        return ",".join([str(pid) for pid in obj.old_pgpids]) if obj.old_pgpids else "-"

    @admin.display(
        description="Standard date",
    )
    def standard_date(self, obj):
        return standard_date_display(obj.doc_date_standard)

    @admin.display(description="Cite description")
    def cite_description(self, _):
        return "The authors selected below will appear in the citation at the bottom of the public document page."

    list_filter = (
        "doctype",
        HasTranscriptionListFilter,
        HasTranslationListFilter,
        (
            "textblock__fragment__iiif_url",
            custom_empty_field_list_filter("IIIF image", "Has image", "No image"),
        ),
        (
            "needs_review",
            custom_empty_field_list_filter("review status", "Needs review", "OK"),
        ),
        "status",
        DateAfterListFilter,
        DateBeforeListFilter,
        InferredDatingListFilter,
        ("textblock__fragment__collection", admin.RelatedOnlyFieldListFilter),
        ("languages", admin.RelatedOnlyFieldListFilter),
        ("secondary_languages", admin.RelatedOnlyFieldListFilter),
    )

    # organize into fieldsets so that we can insert inlines mid-form
    fieldsets = (
        (
            None,
            {
                "fields": (
                    (
                        "shelfmark",
                        "id",
                        "view_old_pgpids",
                        "fragment_historical_shelfmarks",
                    ),
                    "shelfmark_override",
                    "doctype",
                    ("languages", "secondary_languages"),
                    "language_note",
                    "description",
                )
            },
        ),
        (
            None,
            {
                "fields": (
                    (
                        "doc_date_original",
                        "doc_date_calendar",
                        "doc_date_standard",
                        "standard_date",
                    ),
                ),
            },
        ),
        (
            None,
            {
                "fields": (
                    "tags",
                    "status",
                    ("needs_review", "notes"),
                    "image_overrides",
                    "admin_thumbnails",
                )
            },
        ),
        # edition, translation
    )
    autocomplete_fields = ["languages", "secondary_languages"]
    # NOTE: autocomplete does not honor limit_choices_to in model
    inlines = [
        DocumentDatingInline,
        DocumentTextBlockInline,
        DocumentFootnoteInline,
        DocumentPersonInline,
        DocumentPlaceInline,
        DocumentEventInline,
    ]
    # mixed fieldsets and inlines: /templates/admin/snippets/mixed_inlines_fieldsets.html
    fieldsets_and_inlines_order = (
        "f",  # shelfmark, languages, description fieldset
        "f",  # date on document fieldset
        "i",  # DocumentDatingInline
        "f",  # tags, status, order override fieldset
        "itt",  # images/transcription/translation panel
        "i",  # DocumentTextBlockInline
        "i",  # DocumentFootnoteInline
        "i",  # DocumentPersonInline
        "i",  # DocumentPlaceInline
        "i",  # DocumentEventInline
    )

    class Media:
        css = {"all": ("css/admin-local.css",)}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # override to alphabetize doctype dropdown
        if db_field.name == "doctype":
            kwargs["queryset"] = DocumentType.objects.order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        # Override to inject help text into display field
        help_texts = {
            "admin_thumbnails": """Drag image thumbnails to customize order when necessary (i.e.
            image sequence does not follow fragment/shelfmark sequence). Click rotation buttons to
            rotate images, and use checkboxes to select or deselect images as part of the document.
            Changes will be applied on save. NOTE: Deselecting ALL images from a fragment will
            be treated the same as selecting all images from that fragment, since a fragment must
            have at least one selected image; if not, the fragment should be removed from the document."""
        }
        kwargs.update({"help_texts": help_texts})
        return super().get_form(request, obj, **kwargs)

    def get_deleted_objects(self, objs, request):
        # override to remove log entries from list and permission check
        (
            deletable_objects,
            model_count,
            perms_needed,
            protected,
        ) = super().get_deleted_objects(objs, request)

        if "log entries" in model_count:
            # remove any counts for log entries
            del model_count["log entries"]
            # remove the permission needed for log entry deletion
            perms_needed.remove("log entry")
            # filter out Log Entry from the list of items to be displayed for deletion
            deletable_objects = [
                obj
                for obj in deletable_objects
                if not isinstance(obj, str) or not obj.startswith("Log entry:")
            ]
        return deletable_objects, model_count, perms_needed, protected

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .metadata_prefetch()
            .prefetch_related("footnotes")
            .annotate(shelfmk_all=ArrayAgg("textblock__fragment__shelfmark"))
            .order_by("shelfmk_all")
        )

    def get_search_results(self, request, queryset, search_term):
        """Override admin search to use Solr."""

        # use inherited method if this is an autocomplete search
        if request and request.path == "/admin/autocomplete/":
            return super().get_search_results(request, queryset, search_term)
        # otherwise, if search term is not blank, filter the queryset via solr search
        elif search_term:
            # - use AND instead of OR to get smaller result sets, more
            #  similar to default admin search behavior
            # - return pks for all matching records
            sqs = (
                DocumentSolrQuerySet()
                .admin_search(search_term)
                .only("pgpid")
                .get_results(rows=100000)
            )
            pks = [r["pgpid"] for r in sqs]
            # filter queryset by id if there are results
            if sqs:
                queryset = queryset.filter(pk__in=pks)
            else:
                queryset = queryset.none()

        # return queryset, use distinct not needed
        return queryset, False

    def save_model(self, request, obj, form, change):
        """Customize this model's save_model function and then execute the
        existing admin.ModelAdmin save_model function"""
        if "_saveasnew" in request.POST:
            # Get the ID from the admin URL
            original_pk = resolve(request.path).kwargs["object_id"]
            # Get the original object
            original_doc = obj._meta.concrete_model.objects.get(id=original_pk)
            clone_message = f"Cloned from {str(original_doc)}"
            obj.notes = "\n".join([val for val in (obj.notes, clone_message) if val])
            # update date created & modified so they are accurate
            # for the new model
            obj.created = timezone.now()
            obj.last_modified = None

        # set request on the object so that save method can send messages
        # if there is an error converting the date
        obj.request = request
        super().save_model(request, obj, form, change)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Customize this model's change_view to add IIIF images and default/disabled panels
        to context for transcription/translation viewer, then execute existing change_view
        """
        extra_ctx = extra_context or {}
        document = self.get_object(request, object_id)
        if document:
            # get images
            images = document.iiif_images(with_placeholders=True)
            # get available digital content panels
            available_panels = document.available_digital_content
            extra_ctx.update(
                {
                    "images": images,
                    # show all available panels by default
                    "default_shown": available_panels,
                    # disable any unavailable panels
                    "disabled": [
                        panel
                        for panel in ["images", "translation", "transcription"]
                        if panel not in available_panels
                    ],
                }
            )
        return super().change_view(
            request, object_id, form_url, extra_context=extra_ctx
        )

    def history_view(self, request, object_id, extra_context=None):
        """Customize this model's history_view to add histories for all the
        footnotes and annotations related to this document to context, then
        execute existing history_view"""
        document = self.get_object(request, unquote(object_id))
        # get related footnote log entries
        footnote_pks = document.footnotes.all().values_list("pk", flat=True)
        footnote_action_list = (
            LogEntry.objects.filter(
                object_id__in=[str(pk) for pk in footnote_pks],
                content_type=ContentType.objects.get(
                    app_label="footnotes", model="footnote"
                ),
            )
            .select_related()
            .order_by("action_time")
        )
        # get related annotation log entries
        annotations = Annotation.objects.filter(footnote__pk__in=footnote_pks)
        annotation_action_list = (
            LogEntry.objects.filter(
                object_id__in=[
                    str(pk) for pk in annotations.values_list("pk", flat=True)
                ],
                content_type=ContentType.objects.get(
                    app_label="annotations", model="annotation"
                ),
            )
            .select_related()
            .order_by("action_time")
        )
        extra_ctx = extra_context or {}
        extra_ctx.update(
            {
                "footnote_action_list": footnote_action_list,
                "annotation_action_list": annotation_action_list,
            }
        )
        return super().history_view(request, object_id, extra_context=extra_ctx)

    @admin.display(description="Merge selected documents")
    def merge_documents(self, request, queryset=None):
        """Admin action to merge selected documents. This action redirects to an intermediate
        page, which displays a form to review for confirmation and choose the primary document before merging.
        """
        # Functionality drawn from https://github.com/Princeton-CDH/mep-django/blob/main/mep/people/admin.py

        # NOTE: using selected ids from form and ignoring queryset
        # because we can't pass the queryset via redirect
        selected = request.POST.getlist("_selected_action")
        if len(selected) < 2:
            messages.error(request, "You must select at least two documents to merge")
            return HttpResponseRedirect(reverse("admin:corpus_document_changelist"))
        return HttpResponseRedirect(
            "%s?ids=%s" % (reverse("admin:document-merge"), ",".join(selected)),
            status=303,
        )  # status code 303 means "See Other"

    @admin.display(description="Export selected documents to CSV")
    def export_to_csv(self, request, queryset=None):
        """Stream tabular data as a CSV file"""
        queryset = queryset or self.get_queryset(request)
        exporter = AdminDocumentExporter(queryset=queryset, progress=False)
        return exporter.http_export_data_csv()

    def get_urls(self):
        """Return admin urls; adds a custom URL for exporting all documents
        as CSV"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="corpus_document_csv",
            ),
            path(
                "merge/",
                DocumentMerge.as_view(),
                name="document-merge",
            ),
        ]
        return urls + super(DocumentAdmin, self).get_urls()

    # -------------------------------------------------------------------------

    actions = (export_to_csv, merge_documents)


@admin.register(DocumentType)
class DocumentTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    list_display = ("name", "display_label")

    class Media:
        css = {"all": ("css/admin-local.css",)}


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    list_display = ("shelfmark", "collection_display", "url", "is_multifragment")
    search_fields = ("shelfmark", "old_shelfmarks", "notes", "needs_review")
    readonly_fields = ("created", "last_modified", "iiif_provenance")
    list_filter = (
        ("url", custom_empty_field_list_filter("IIIF image", "Has image", "No image")),
        (
            "needs_review",
            custom_empty_field_list_filter("review status", "Needs review", "OK"),
        ),
        "is_multifragment",
        ("collection", admin.RelatedOnlyFieldListFilter),
    )
    inlines = [FragmentTextBlockInline]
    list_editable = ("url",)
    fields = (
        ("shelfmark", "old_shelfmarks"),
        "collection",
        ("url", "iiif_url"),
        "is_multifragment",
        "provenance_display",
        "material_support",
        "provenance",
        "iiif_provenance",
        "notes",
        "needs_review",
        ("created", "last_modified"),
    )

    # default ordering on Collection uses concat with field references,
    # which does not work when referenced from another model;
    # as a workaround,add a display property that makes the custom sort
    # relative to the fragment
    def collection_display(self, obj):
        return obj.collection

    collection_display.verbose_name = "Collection"
    collection_display.admin_order_field = Concat(
        F("collection__lib_abbrev"),
        F("collection__abbrev"),
        F("collection__name"),
        F("collection__library"),
    )

    def save_model(self, request, obj, form, change):
        # pass request in to save so that we can send messages
        # if there is an error loading the IIIF manifest
        obj.request = request
        super().save_model(request, obj, form, change)

    @admin.display(description="Export selected fragments to CSV")
    def export_to_csv(self, request, queryset=None):
        """Stream tabular data as a CSV file"""
        queryset = queryset or self.get_queryset(request)
        exporter = AdminFragmentExporter(queryset=queryset, progress=False)
        return exporter.http_export_data_csv()

    def get_urls(self):
        """Return admin urls; adds a custom URL for exporting all sources
        as CSV"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="corpus_fragments_csv",
            )
        ]
        return urls + super().get_urls()

    actions = (export_to_csv,)


@admin.register(Provenance)
class ProvenanceAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    search_fields = ("name",)
    fields = ("name",)
    ordering = ("name",)


@admin.register(MaterialSupport)
class MaterialSupportAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    search_fields = ("name",)
    fields = ("name",)
    ordering = ("name",)
