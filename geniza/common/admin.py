from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User


class LocalUserAdmin(UserAdmin):
    """Extends :class:`django.contribut.auth.admin.UserAdmin`
    to provide additional detail for user administration."""

    list_display = UserAdmin.list_display + (
        "is_superuser",
        "is_active",
        "last_login",
        "group_names",
    )

    def group_names(self, obj):
        """Custom property to display group membership."""
        if obj.groups.exists():
            return ", ".join(g.name for g in obj.groups.all())

    group_names.short_description = "groups"


admin.site.unregister(User)
admin.site.register(User, LocalUserAdmin)
