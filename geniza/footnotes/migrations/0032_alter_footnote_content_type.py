# Generated by Django 3.2.16 on 2023-10-12 20:16

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("footnotes", "0031_unspecified_source_language"),
    ]

    operations = [
        migrations.AlterField(
            model_name="footnote",
            name="content_type",
            field=models.ForeignKey(
                limit_choices_to=models.Q(
                    ("app_label", "corpus"), ("app_label", "entities"), _connector="OR"
                ),
                on_delete=django.db.models.deletion.CASCADE,
                to="contenttypes.contenttype",
            ),
        ),
    ]