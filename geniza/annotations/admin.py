import pprint

from django.contrib import admin
from django.utils.safestring import mark_safe

from geniza.annotations.models import Annotation


class AnnotationAdmin(admin.ModelAdmin):
    readonly_fields = (
        "uri",
        "created",
        "modified",
        "display_content",
        "canonical",
        "via",
    )
    fields = ["uri", "display_content", "created", "modified", "canonical", "via"]
    list_display = ["id", "pgpid", "target_id", "created", "modified"]
    search_fields = ("id", "content")

    def display_content(self, obj):
        """format json content for display in admin"""
        return mark_safe("<pre>%s</pre>" % pprint.pformat(obj.content, indent=2))

    def pgpid(self, obj):
        """retrieve pgpid from manifest if available; assumes geniza manifest structure"""
        try:
            manifest = obj.content["target"]["source"]["partOf"]["id"]
            return manifest.strip("/").split("/")[-3]
        except (KeyError, TypeError):
            return

    def target_id(self, obj):
        """retrieve target id from content if available"""
        try:
            return obj.content["target"]["source"]["id"]
        except (KeyError, TypeError):
            pass


admin.site.register(Annotation, AnnotationAdmin)

# Register your models here.
