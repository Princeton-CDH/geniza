import pprint
from html import escape

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
        "footnote",
    )
    fields = [
        "uri",
        "display_content",
        "created",
        "modified",
        "canonical",
        "via",
        "footnote",
    ]
    list_display = ["id", "pgpid", "target_id", "created", "modified"]
    search_fields = ("id", "content")

    def display_content(self, obj):
        """format json content for display in admin"""
        # use mark_safe to render <pre>, use escape() to prevent rendering content HTML
        return mark_safe(
            "<pre>%s</pre>" % escape(pprint.pformat(obj.content, indent=1))
        )

    def pgpid(self, obj):
        """retrieve pgpid from associated footnote"""
        return obj.footnote.content_object.pk

    def target_id(self, obj):
        """retrieve target id from content if available"""
        try:
            return obj.content["target"]["source"]["id"]
        except (KeyError, TypeError):
            pass


admin.site.register(Annotation, AnnotationAdmin)
