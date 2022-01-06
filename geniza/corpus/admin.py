from collections import namedtuple

from adminsortable2.admin import SortableInlineAdminMixin
from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db.models import CharField, Count, F, Q
from django.db.models.functions import Concat
from django.db.models.query import Prefetch, QuerySet
from django.forms.widgets import Textarea, TextInput
from django.urls import path, resolve, reverse
from django.utils import timezone
from django.utils.html import format_html
from tabular_export.admin import export_to_csv_response

from geniza.common.admin import custom_empty_field_list_filter
from geniza.common.utils import absolutize_url
from geniza.corpus.models import (
    Collection,
    Document,
    DocumentNeedsReview,
    DocumentPrefetchableProxy,
    DocumentType,
    Fragment,
    LanguageScript,
    TextBlock,
)
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
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
    readonly_fields = ("document_link", "document_description")
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
    search_fields = ("language", "script", "display_name")

    class Media:
        css = {"all": ("css/admin-local.css",)}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                Count("document", distinct=True),
                Count("secondary_document", distinct=True),
            )
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
    readonly_fields = ("thumbnail",)
    fields = (
        "fragment",
        "multifragment",
        "side",
        "region",
        "order",
        "certain",
        "thumbnail",
    )
    extra = 1
    formfield_overrides = {CharField: {"widget": TextInput(attrs={"size": "10"})}}


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        exclude = ()
        widgets = {
            "language_note": Textarea(attrs={"rows": 1}),
            "needs_review": Textarea(attrs={"rows": 3}),
            "notes": Textarea(attrs={"rows": 3}),
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


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentForm
    list_display = (
        "id",
        "shelfmark",
        "description",
        "doctype",
        "all_tags",
        "all_languages",
        "last_modified",
        "has_transcription",
        "has_image",
        "is_public",
    )
    readonly_fields = ("created", "last_modified", "shelfmark", "id", "view_old_pgpids")
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
        (
            "footnotes__content",
            custom_empty_field_list_filter(
                "transcription", "Has transcription", "No transcription"
            ),
        ),
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
        "doctype",
        ("languages", "secondary_languages"),
        "language_note",
        "description",
        ("doc_date_original", "doc_date_calendar", "doc_date_standard"),
        "tags",
        "status",
        ("needs_review", "notes"),
        # edition, translation
    )
    autocomplete_fields = ["languages", "secondary_languages"]
    # NOTE: autocomplete does not honor limit_choices_to in model
    inlines = [DocumentTextBlockInline, DocumentFootnoteInline]

    class Media:
        css = {"all": ("css/admin-local.css",)}

    def get_queryset(self, request):
        return (
            DocumentPrefetchableProxyAdmin(DocumentPrefetchableProxy, self.admin_site)
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
        super().save_model(request, obj, form, change)

    # CSV EXPORT -------------------------------------------------------------

    def csv_filename(self):
        """Generate filename for CSV download"""
        return f'geniza-documents-{timezone.now().strftime("%Y%m%dT%H%M%S")}.csv'

    def tabulate_queryset(self, queryset):
        """Generator for data in tabular form, including custom fields"""

        script_user = settings.SCRIPT_USERNAME
        # generate absolute urls locally with a single db call,
        # instead of calling out to absolutize_url method
        site_domain = Site.objects.get_current().domain.rstrip("/")
        # qa / prod always https
        url_scheme = "https://"

        for doc in queryset:

            all_textblocks = doc.textblock_set.all()
            all_fragments = [tb.fragment for tb in all_textblocks]
            all_log_entries = doc.log_entries.all()
            input_users = set(
                [
                    log_entry.user
                    for log_entry in all_log_entries
                    if log_entry.user.username != script_user
                ]
            )
            iiif_urls = [fr.iiif_url for fr in all_fragments]
            view_urls = [fr.url for fr in all_fragments]
            multifrag = [tb.multifragment for tb in all_textblocks]
            side = [tb.get_side_display() for tb in all_textblocks]
            region = [tb.region for tb in all_textblocks]
            old_shelfmarks = [fragment.old_shelfmarks for fragment in all_fragments]
            libraries = set(
                [
                    fragment.collection.lib_abbrev or fragment.collection.library
                    if fragment.collection
                    else ""
                    for fragment in all_fragments
                ]
            ) - {
                ""
            }  # exclude empty string for any fragments with no library
            collections = set(
                [
                    fragment.collection.abbrev or fragment.collection.name
                    if fragment.collection
                    else ""
                    for fragment in all_fragments
                ]
            ) - {
                ""
            }  # exclude empty string for any with no collection

            yield [
                doc.id,  # pgpid
                # to make the download as efficient as possible, don't use
                # absolutize_url, reverse, or get_absolute_url methods
                f"{url_scheme}{site_domain}/documents/{doc.id}/",  # public site url
                ";".join(iiif_urls) if any(iiif_urls) else "",
                ";".join(view_urls) if any(view_urls) else "",
                doc.shelfmark,  # shelfmark
                ";".join([s for s in multifrag if s]),
                ";".join([s for s in side if s]),  # side (recto/verso)
                ";".join([r for r in region if r]),  # text block region
                doc.doctype,
                doc.all_tags(),
                doc.description,
                ";".join([os for os in old_shelfmarks if os]),
                doc.all_languages(),
                doc.all_secondary_languages(),
                doc.language_note,
                doc.doc_date_original,
                doc.doc_date_calendar,
                doc.doc_date_standard,
                doc.notes,
                doc.needs_review,
                f"{url_scheme}{site_domain}/admin/corpus/document/{doc.id}/change/",
                # default sort is most recent first, so initial input is last
                all_log_entries.last().action_time if all_log_entries else "",
                doc.last_modified,
                ";".join(
                    set([user.get_full_name() or user.username for user in input_users])
                ),  # input by
                doc.get_status_display(),
                ";".join(libraries) if any(libraries) else "",
                ";".join(collections) if any(collections) else "",
            ]

    csv_fields = [
        "pgpid",
        "url",
        "iiif_urls",
        "fragment_urls",
        "shelfmark",
        "multifragment",
        "side",
        "region",
        "type",
        "tags",
        "description",
        "shelfmarks_historic",
        "languages_primary",
        "languages_secondary",
        "language_note",
        "doc_date_original",
        "doc_date_calendar",
        "doc_date_standard",
        "notes",
        "needs_review",
        "url_admin",
        "initial_entry",
        "last_modified",
        "input_by",
        "status",
        "library",
        "collection",
    ]

    @admin.display(description="Export selected documents to CSV")
    def export_to_csv(self, request, queryset=None):
        """Stream tabular data as a CSV file"""
        queryset = queryset or self.get_queryset(request)
        # additional prefetching needed to optimize csv export but
        # not needed for admin list view
        queryset = queryset.order_by("id").prefetch_related(
            "secondary_languages",
            "log_entries",
        )

        return export_to_csv_response(
            self.csv_filename(),
            self.csv_fields,
            self.tabulate_queryset(queryset),
        )

    def get_urls(self):
        """Return admin urls; adds a custom URL for exporting all documents
        as CSV"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="corpus_document_csv",
            )
        ]
        return urls + super(DocumentAdmin, self).get_urls()

    # -------------------------------------------------------------------------

    actions = (export_to_csv,)


@admin.register(DocumentNeedsReview)
class DocumentNeedsReviewAdmin(DocumentAdmin):
    ordering = ("needs_review",)

    list_display = (
        "needs_review",
        "id",
        "shelfmark",
        "description",
        "doctype",
        "all_languages",
        "last_modified",
        "is_public",
    )

    def get_queryset(self, request):
        # ?: We often use `needs_review__is_empty` but I got this error. Is that expected?
        #      Unsupported lookup 'isempty' for TextField or join on the field not permitted.
        return super().get_queryset(request).exclude(needs_review="")


class DocumentPrefetchableProxyAdmin(admin.ModelAdmin):
    """Proxy model admin for :class:`DocumentPrefetchableProxy` that intercepts `get_queryset`
    in order to prefetch the :class:`GenericRelation` `log_entries`."""

    def get_queryset(self, request):
        return super().get_queryset(request)

    def filter(self, request):
        return super().filter(request)


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
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
