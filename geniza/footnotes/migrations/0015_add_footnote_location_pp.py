# Generated by Django 3.2.6 on 2021-12-15 21:28

from django.db import migrations
from django.db.models import F, Value
from django.db.models.functions import Concat


def add_pp_to_footnote_pages(apps, schema_editor):
    # for footnotes that start with with a numeric location,
    # we want to add pp. to make the meaning clearer
    # on the front end
    Footnote = apps.get_model("footnotes", "Footnote")

    # find and update footnotes to based on location contents

    # first, find footnotes with purely numeric location (i.e., single page number)
    # prefix with p.
    Footnote.objects.filter(location__regex=r"^\d+$").update(
        location=Concat(Value("p. "), F("location"))
    )

    # next, find footnotes that start with numeric values
    # - exclude location that starts with numeric followed by a hebrew letter
    #   (currently only one, 49ב) — this is a document location, not a page number
    # - find all other footnotes with locations that start with a number
    Footnote.objects.exclude(location__regex=r"^\d+[\u0590-\u05fe]").filter(
        location__regex=r"^\d"
    ).update(location=Concat(Value("pp. "), F("location")))


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0014_alter_source_edition"),
    ]

    operations = [
        migrations.RunPython(add_pp_to_footnote_pages, migrations.RunPython.noop)
    ]
