from admin_log_entries.admin import LogEntryAdmin
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.forms import ModelForm, ValidationError
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from taggit.admin import TagAdmin
from taggit.models import Tag

from geniza.common.metadata_export import LogEntryExporter
from geniza.common.models import UserProfile
from geniza.corpus.views import TagMerge


class TypedRelationInline:
    """admin inline for a relation referencing a separate model for relationship type"""

    def get_formset(self, request, obj=None, **kwargs):
        """Override in order to remove the delete button from the type field"""
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields["type"].widget.can_delete_related = False
        return formset


class UserProfileInline(admin.StackedInline):
    """admin inline for editing custom user profile information"""

    # NOTE: using stacked inline so that github help text is displayed
    # with the link to github docs clickable
    model = UserProfile
    autocomplete_fields = ["creator"]
    fields = ("github_coauthor", "creator")


class LocalUserAdmin(UserAdmin):
    """Extends :class:`django.contrib.auth.admin.UserAdmin`
    to provide additional detail for user administration."""

    list_display = UserAdmin.list_display + (
        "is_superuser",
        "is_active",
        "last_login",
        "group_names",
    )

    inlines = [UserProfileInline]

    def group_names(self, obj):
        """Custom property to display group membership."""
        if obj.groups.exists():
            return ", ".join(g.name for g in obj.groups.all())

    group_names.short_description = "groups"


def custom_empty_field_list_filter(title, non_empty_label=None, empty_label=None):
    """Generates a :class:`django.contrib.admin.EmptyFieldListFilter` with a
    custom title and empty/non-empty option labels."""

    class CustomEmptyFieldListFilter(admin.EmptyFieldListFilter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.title = title

        def choices(self, changelist):
            choices = list(super().choices(changelist))
            if empty_label:
                choices[1]["display"] = empty_label
            if non_empty_label:
                choices[2]["display"] = non_empty_label
            return choices

    return CustomEmptyFieldListFilter


# unregister default taggit admin so we can register our own
admin.site.unregister(Tag)


class TagForm(ModelForm):
    """
    Extends the default tag admin form to validate uniqueness, case-insensitive,
    on tag names.

    NOTE: This is needed because the Tag model does not have a DB-level case-insensitive uniqueness
    constraint applied out of the box, and adding such a constraint is not trivial at the moment.
    TODO: Once Django is updated past 4.0, a "functional unique constraint" may be added to a custom
    Tag model to solve this problem; then, this form override will no longer be needed.
    """

    class Meta:
        model = Tag
        exclude = ()

    def clean(self):
        # super().clean() will handle slug validation
        super().clean()
        # check if this is a duplicate (case-insensitive)
        name = self.cleaned_data.get("name")
        tags_name = Tag.objects.filter(name__iexact=name)
        if self.instance:
            # exclude self from search if this record exists
            tags_name = tags_name.exclude(pk=self.instance.pk)
        if tags_name.exists():
            # if there are any identical tags, validation error
            self.add_error(
                "name", ValidationError(f'Tag with the name "{name}" already exists.')
            )
        return self.cleaned_data


@admin.register(Tag)
class CustomTagAdmin(TagAdmin):
    list_display = ("name", "slug", "item_count")
    form = TagForm

    @admin.display(description="Merge selected tags")
    def merge_tags(self, request, queryset=None):
        """Admin action to merge selected tags. This action redirects to an intermediate
        page, which displays a form to review for confirmation and choose the primary tag before merging.
        """
        # Adapted from corpus.admin.DocumentAdmin.merge_documents

        # NOTE: using selected ids from form and ignoring queryset
        # because we can't pass the queryset via redirect
        selected = request.POST.getlist("_selected_action")
        if len(selected) < 2:
            messages.error(request, "You must select at least two tags to merge")
            return HttpResponseRedirect(reverse("admin:taggit_tag_changelist"))
        return HttpResponseRedirect(
            "%s?ids=%s" % (reverse("admin:tag-merge"), ",".join(selected)),
            status=303,
        )  # status code 303 means "See Other"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                # taggit_taggeditem_items is the reference to the taggeditem object
                item_count=Count("taggit_taggeditem_items", distinct=True),
            )
        )

    def get_urls(self):
        """Return admin urls; adds a custom URL for tag merge"""
        urls = [
            path(
                "merge/",
                TagMerge.as_view(),
                name="tag-merge",
            ),
        ]
        return urls + super().get_urls()

    def item_count(self, obj):
        return obj.item_count

    item_count.admin_order_field = "item_count"
    item_count.short_description = "count"

    actions = (merge_tags,)


admin.site.unregister(User)
admin.site.register(User, LocalUserAdmin)


class LocalLogEntryAdmin(LogEntryAdmin):
    @admin.display(description="Export selected log entries to CSV")
    def export_to_csv(self, request, queryset=None):
        """Stream tabular data as a CSV file"""
        queryset = queryset or self.get_queryset(request)
        exporter = LogEntryExporter(queryset=queryset, progress=False)
        return exporter.http_export_data_csv()

    def get_urls(self):
        """Return admin urls; adds a custom URL for exporting all documents
        as CSV"""
        urls = [
            path(
                "csv/",
                self.admin_site.admin_view(self.export_to_csv),
                name="admin_logentry_csv",
            ),
        ]
        return urls + super().get_urls()

    actions = (export_to_csv,)


admin.site.unregister(LogEntry)
admin.site.register(LogEntry, LocalLogEntryAdmin)


class PreventLogEntryDeleteMixin:
    """Mixin required for ModelAdmins for all classes with a GenericRelation to LogEntry,
    to prevent LogEntries from being counted as related objects to be deleted."""

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
