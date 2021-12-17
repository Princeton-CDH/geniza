from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin
from wagtail.documents.models import Document
from wagtail.images.models import Image

from .models import Contributor

# unregister wagtail content from django admin to avoid
# editing something in the wrong place and potentially causing
# problems

# adapted from mep-django

admin.site.unregister(Image)
admin.site.unregister(Document)

# Set up tabbed translation admin for contributors
@admin.register(Contributor)
class ContributorAdmin(TabbedTranslationAdmin):
    list_display = ("last_name", "first_name", "role")
    search_fields = ("first_name", "last_name", "role")
    fields = ("last_name", "first_name", "role")
