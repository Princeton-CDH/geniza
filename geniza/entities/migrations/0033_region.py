# Generated by Django 3.2.23 on 2025-06-13 17:02

import django.db.models.deletion
from django.contrib.auth.management import create_permissions
from django.db import migrations, models

CONTENT_EDITOR = "Content Editor"
# new permissions for content editor
content_editor_perms = ["view_region"]

CONTENT_ADMIN = "Content Admin"
# additional new permissions for content admin: add, change, delete regions
content_admin_perms = ["add_region", "change_region", "delete_region"]


def set_region_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # make sure permissions are created before loading the fixture
    # which references them
    # (when running migrations all at once, permissions may not yet exist)
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    editor_group = Group.objects.get(name=CONTENT_EDITOR)
    permissions = []
    for codename in content_editor_perms:
        # using explicit get so that there will be an error if an
        # expected permission is not found
        permissions.append(Permission.objects.get(codename=codename))
    editor_group.permissions.add(*permissions)

    # update content admin group; add to content edit permissions
    admin_group = Group.objects.get(name=CONTENT_ADMIN)
    for codename in content_admin_perms:
        permissions.append(Permission.objects.get(codename=codename))
    admin_group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("entities", "0032_person_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="Region",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name="place",
            name="containing_region",
            field=models.ForeignKey(
                help_text="The geographic region containing this place. For internal use and CSV exports only.",
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="entities.region",
            ),
        ),
        migrations.RunPython(
            set_region_permissions, reverse_code=migrations.RunPython.noop
        ),
    ]
