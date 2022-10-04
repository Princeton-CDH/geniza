from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db.models import CharField, Count, F
from django.db.models.functions import Concat
from django.db.models.query import Prefetch
from django.forms.widgets import HiddenInput, Textarea, TextInput
from django.http import HttpResponseRedirect
from django.urls import path, resolve, reverse
from django.utils import timezone
from django.utils.html import format_html
from import_export.admin import ExportActionMixin, ExportMixin
from modeltranslation.admin import TabbedTranslationAdmin
from tabular_export.admin import export_to_csv_response

from geniza.common.admin import custom_empty_field_list_filter
from geniza.corpus.models import (
    Collection,
    Document,
    DocumentType,
    Fragment,
    LanguageScript,
    TextBlock,
)
from geniza.corpus.resource import DocumentResource
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.views import DocumentMerge
from geniza.footnotes.admin import DocumentFootnoteInline


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
    )
    fields = (
        "fragment",
        "multifragment",
        "side",
        "region",
        "order",
        "certain",
        "thumbnail",
        "selected_images",
    )
    extra = 1
    formfield_overrides = {
        CharField: {"widget": TextInput(attrs={"size": "10"})},
        ArrayField: {"widget": HiddenInput()},  # hidden input for selected_images
    }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        exclude = ()
        widgets = {
            "language_note": Textarea(attrs={"rows": 1}),
            "needs_review": Textarea(attrs={"rows": 3}),
            "notes": Textarea(attrs={"rows": 3}),
            "image_order_override": HiddenInput(),
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
            return queryset.filter(footnotes__content__has_key="html")
        if self.value() == "no":
            return queryset.exclude(footnotes__content__has_key="html")


@admin.register(Document)
class DocumentAdmin(
    ExportActionMixin,
    ExportMixin,
    TabbedTranslationAdmin,
    SortableAdminBase,
    admin.ModelAdmin,
):
    resource_class = DocumentResource  # resource for export
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
    )
    search_fields = (
        "fragments__shelfmark",
        "tags__name",
        "description",
        "notes",
        "needs_review",
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

    list_filter = (
        "doctype",
        HasTranscriptionListFilter,
        (
            "textblock__fragment__iiif_url",
            custom_empty_field_list_filter("IIIF image", "Has image", "No image"),
        ),
        (
            "needs_review",
            custom_empty_field_list_filter("review status", "Needs review", "OK"),
        ),
        "status",
        ("textblock__fragment__collection", admin.RelatedOnlyFieldListFilter),
        ("languages", admin.RelatedOnlyFieldListFilter),
        ("secondary_languages", admin.RelatedOnlyFieldListFilter),
    )

    fields = (
        ("shelfmark", "id", "view_old_pgpids"),
        "shelfmark_override",
        "doctype",
        ("languages", "secondary_languages"),
        "language_note",
        "description",
        (
            "doc_date_original",
            "doc_date_calendar",
            "doc_date_standard",
            "standard_date",
        ),
        "tags",
        "status",
        ("needs_review", "notes"),
        "image_order_override",
        "admin_thumbnails",
        # edition, translation
    )
    autocomplete_fields = ["languages", "secondary_languages"]
    # NOTE: autocomplete does not honor limit_choices_to in model
    inlines = [DocumentTextBlockInline, DocumentFootnoteInline]

    class Media:
        css = {"all": ("css/admin-local.css",)}

    def get_form(self, request, obj=None, **kwargs):
        # Override to inject help text into display field
        help_texts = {
            "admin_thumbnails": "Drag image thumbnails to customize order when necessary (i.e. image sequence does not follow fragment/shelfmark sequence)"
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
            .select_related(
                "doctype",
            )
            .prefetch_related(
                "tags",
                "languages",
                # Optimize lookup of fragments in two steps: prefetch_related on
                # TextBlock, then select_related on Fragment.
                #
                # prefetch_related works on m2m and generic relationships and
                # operates at the python level, while select_related only works
                # on fk or one-to-one and operates at the database level. We
                # can chain the latter onto the former because TextBlocks have
                # only one Fragment.
                #
                # For more, see:
                # https://docs.djangoproject.com/en/3.2/ref/models/querysets/#prefetch-related
                Prefetch(
                    "textblock_set",
                    queryset=TextBlock.objects.select_related(
                        "fragment", "fragment__collection"
                    ),
                ),
                "footnotes__content__isnull",
            )
            .annotate(shelfmk_all=ArrayAgg("textblock__fragment__shelfmark"))
            .order_by("shelfmk_all")
        )

    def get_search_results(self, request, queryset, search_term):
        """Override admin search to use Solr."""

        # if search term is not blank, filter the queryset via solr search
        if search_term:
            # - use AND instead of OR to get smaller result sets, more
            #  similar to default admin search behavior
            # - return pks for all matching records
            sqs = (
                DocumentSolrQuerySet()
                .admin_search(search_term)
                .raw_query_parameters(**{"q.op": "AND"})
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

    # CSV EXPORT -------------------------------------------------------------
    # ...

    @admin.display(description="Merge selected documents")
    def merge_documents(self, request, queryset=None):
        """Admin action to merge selected documents. This action redirects to an intermediate
        page, which displays a form to review for confirmation and choose the primary document before merging."""
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

    def get_urls(self):
        """Return admin urls; adds a custom URL for exporting all documents
        as CSV"""
        urls = [
            # path(
            #     "csv/",
            #     self.admin_site.admin_view(self.export_to_csv),
            #     name="corpus_document_csv",
            # ),
            path(
                "merge/",
                DocumentMerge.as_view(),
                name="document-merge",
            ),
        ]
        return urls + super(DocumentAdmin, self).get_urls()

    # -------------------------------------------------------------------------

    # actions = (export_to_csv, merge_documents)
    actions = (merge_documents,)


@admin.register(DocumentType)
class DocumentTypeAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    list_display = ("name", "display_label")


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    list_display = ("shelfmark", "collection_display", "url", "is_multifragment")
    search_fields = ("shelfmark", "old_shelfmarks", "notes", "needs_review")
    readonly_fields = ("created", "last_modified")
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


### New exporter code
