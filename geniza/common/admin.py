from admin_log_entries.admin import LogEntryAdmin
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.urls import path
from taggit.admin import TagAdmin
from taggit.models import Tag

from geniza.common.metadata_export import LogEntryExporter
from geniza.common.models import UserProfile


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


@admin.register(Tag)
class CustomTagAdmin(TagAdmin):
    list_display = ("name", "slug", "item_count")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                # taggit_taggeditem_items is the reference to the taggeditem object
                item_count=Count("taggit_taggeditem_items", distinct=True),
            )
        )

    def item_count(self, obj):
        return obj.item_count

    item_count.admin_order_field = "item_count"
    item_count.short_description = "count"


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
