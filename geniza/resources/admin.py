from django.contrib import admin
from django.utils.html import format_html

from geniza.resources.models import Manual


class ManualAdmin(admin.ModelAdmin):
    """Admin section for manuals, training materials, and quick links"""

    list_display = ("name", "url_display")
    search_fields = ("name",)
    ordering = ("name",)

    @admin.display(description="URL")
    def url_display(self, obj):
        """Override URL field display link to open in a new tab, with relevant
        accessibility labels and security risk prevention"""
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener noreferrer" aria-label="{0} (opens in a new tab)">{0}</a>',
            obj.url,
        )


admin.site.register(Manual, ManualAdmin)
