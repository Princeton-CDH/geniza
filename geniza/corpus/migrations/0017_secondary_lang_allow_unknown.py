# Generated by Django 3.1 on 2021-08-18 20:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0016_rename_probable_languages_to_secondary"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="secondary_languages",
            field=models.ManyToManyField(
                blank=True,
                related_name="secondary_document",
                to="corpus.LanguageScript",
            ),
        ),
    ]
