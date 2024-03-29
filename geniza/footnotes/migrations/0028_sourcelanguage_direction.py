# Generated by Django 3.2.16 on 2023-05-01 15:06

from django.db import migrations, models


def set_rtl_langs(apps, schema_editor):
    # set known existing RTL languages' direction to RTL
    SourceLanguage = apps.get_model("footnotes", "SourceLanguage")
    # Arabic, Hebrew, Judaeo-Arabic, and Ottoman Turkish are all RTL
    rtl_langs = SourceLanguage.objects.filter(code__in=["ar", "he", "jrb", "ota"])
    for lang in rtl_langs:
        lang.direction = "rtl"
    SourceLanguage.objects.bulk_update(rtl_langs, ["direction"])


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0027_alter_footnote_doc_relation"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourcelanguage",
            name="direction",
            field=models.CharField(
                choices=[("ltr", "Left to right"), ("rtl", "Right to left")],
                default="ltr",
                max_length=3,
            ),
        ),
        migrations.RunPython(set_rtl_langs, migrations.RunPython.noop),
    ]
