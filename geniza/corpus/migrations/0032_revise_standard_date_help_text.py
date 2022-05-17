# Generated by Django 3.2.13 on 2022-05-16 20:07

import re

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0031_valid_document_doc_date_standard"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="doc_date_calendar",
            field=models.CharField(
                blank=True,
                choices=[
                    ("h", "Hijrī"),
                    ("k", "Kharājī"),
                    ("s", "Seleucid"),
                    ("am", "Anno Mundi"),
                ],
                help_text="Calendar according to which the document gives a date: Hijrī (AH); Kharājī (rare - mostly for fiscal docs); \nSeleucid (sometimes listed as Minyan Shetarot); Anno Mundi (Hebrew calendar)",
                max_length=2,
                verbose_name="Calendar",
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="doc_date_standard",
            field=models.CharField(
                blank=True,
                help_text="CE date (convert to Julian before 1582, Gregorian after 1582). \nUse YYYY, YYYY-MM, YYYY-MM-DD format or YYYY-MM-DD/YYYY-MM-DD for date ranges. \nLeave blank or clear out to automatically calculate standardized date for supported calendars.",
                max_length=255,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile(
                            "^\\d{3,4}(-[01]\\d(-[0-3]\\d)?)?(/\\d{3,4}(-[01]\\d(-[0-3]\\d)?)?)?$"
                        )
                    )
                ],
                verbose_name="Document date (standardized)",
            ),
        ),
    ]