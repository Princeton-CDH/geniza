# Generated by Django 3.2.16 on 2023-03-02 20:17

import re

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0036_collections_merge_jts_ena"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dating",
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
                (
                    "display_date",
                    models.CharField(
                        blank=True,
                        help_text='The dating as it should appear in the public site, such as "Late 12th century"',
                        max_length=255,
                        verbose_name="Display date",
                    ),
                ),
                (
                    "standard_date",
                    models.CharField(
                        help_text="CE date (convert to Julian before 1582, Gregorian after 1582). \nUse YYYY, YYYY-MM, YYYY-MM-DD format or YYYY-MM-DD/YYYY-MM-DD for date ranges.",
                        max_length=255,
                        validators=[
                            django.core.validators.RegexValidator(
                                re.compile(
                                    "^\\d{3,4}(-[01]\\d(-[0-3]\\d)?)?(/\\d{3,4}(-[01]\\d(-[0-3]\\d)?)?)?$"
                                )
                            )
                        ],
                        verbose_name="Standardized date",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        help_text="An explanation for how this date was inferred, and/or by whom"
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="corpus.document",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Inferred datings (not written on the document)",
            },
        ),
    ]
