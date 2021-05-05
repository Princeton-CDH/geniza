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



def custom_empty_field_list_filter(title, non_empty_label=None, empty_label=None):
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

admin.site.unregister(User)
admin.site.register(User, LocalUserAdmin)
