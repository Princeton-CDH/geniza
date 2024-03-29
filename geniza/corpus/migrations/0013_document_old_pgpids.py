# Generated by Django 3.1 on 2021-05-25 02:10

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0012_region_subfragment"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="old_pgpids",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                null=True,
                size=None,
                verbose_name="Old PGPIDs",
            ),
        ),
    ]
