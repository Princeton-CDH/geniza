# Generated by Django 3.2.13 on 2022-09-20 13:09

from django.db import migrations


def link_users_to_creators(apps, schema_editor):
    """ """
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("common", "UserProfile")
    Creator = apps.get_model("footnotes", "Creator")

    for user in User.objects.all():
        creator = Creator.objects.filter(
            first_name_en=user.first_name, last_name_en=user.last_name
        ).first()
        if creator:
            profile = UserProfile.objects.create(user=user, creator=creator)


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0006_userprofile"),
        # initial auth migration: user model must exist
        ("auth", "0001_initial"),
        # initial footnotes migration: creator model must exist
        ("footnotes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(link_users_to_creators, migrations.RunPython.noop),
    ]