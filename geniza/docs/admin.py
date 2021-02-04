from django.contrib import admin

from geniza.docs.models import Library


# register in admin with no customization for now
admin.site.register(Library)
