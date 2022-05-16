# Generated by Django 3.2.13 on 2022-05-10 21:29

from django.db import migrations


def clean_iiif_urls(apps, schema_editor):
    Fragment = apps.get_model("corpus", "Fragment")
    # there are only ~200 of these, so don't worry about efficiency
    for frag in Fragment.objects.filter(iiif_url__contains="?manifest="):
        frag.iiif_url = frag.iiif_url.split("?manifest=")[0]
        frag.save()


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0029_document_shelfmark_override"),
    ]

    operations = [
        migrations.RunPython(clean_iiif_urls, migrations.RunPython.noop),
    ]