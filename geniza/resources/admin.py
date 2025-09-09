from django.contrib import admin

from geniza.resources.models import Manual


class ManualAdmin(admin.ModelAdmin):
    """Admin section for manuals, training materials, and quick links"""

    list_display = ("name", "url")
    search_fields = ("name",)
    ordering = ("name",)


admin.site.register(Manual, ManualAdmin)
