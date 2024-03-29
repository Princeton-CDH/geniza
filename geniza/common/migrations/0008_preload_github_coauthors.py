# Generated by Django 3.2.13 on 2022-09-29 19:22

from django.db import migrations, models

# pre-populate github co-author emails, esp. for users
# who contributed to the tei bitbucket repository
# so they are credited in the export genreated by tei migration

gh_users = {
    "mrustow": "73319225+mrustow@users.noreply.github.com",
    "ae5677": "1414260+alanelbaum@users.noreply.github.com",
    "kryzhova": "105385128+kseniaryzhova@users.noreply.github.com",
    "rkoeser": "rlskoeser@users.noreply.github.com",
    "rrichman": "68028846+richmanrachel@users.noreply.github.com",
    "jp0630": "90917725+jessicazparker@users.noreply.github.com",
    "benj": "benjohnsto@users.noreply.github.com",
    # preloading for convenience, not bitbucket TEI contributors
    "bs9567": "ben@performantsoftware.com",
}


def set_github_coauthors(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("common", "UserProfile")

    # should ignore any users not present in the db
    for user in User.objects.filter(username__in=gh_users.keys()):
        try:
            # set on existing profile if there is one (i.e, user is an author)
            user.profile.github_coauthor = gh_users[user.username]
            user.profile.save()
        except models.ObjectDoesNotExist:
            # otherwise create a new profile
            UserProfile.objects.create(
                user=user, github_coauthor=gh_users[user.username]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0007_link_users_to_creators"),
    ]

    operations = [
        migrations.RunPython(set_github_coauthors, migrations.RunPython.noop),
    ]
