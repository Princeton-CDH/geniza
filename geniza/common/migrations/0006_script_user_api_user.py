# Generated by Django 3.2.13 on 2022-08-25 20:12

from django.conf import settings
from django.db import migrations


def update_script_user(apps, schema_editor):
    # update script user so it can be used for token-based authentication
    # to create annotations via annotation API
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")
    script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
    content_editor = Group.objects.get(name="Content Editor")

    script_user.is_active = True
    script_user.groups.add(content_editor)
    script_user.save()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0005_create_team_user"),
    ]

    operations = [
        migrations.RunPython(
            update_script_user, reverse_code=migrations.RunPython.noop
        ),
    ]