# Generated by Django 3.2.23 on 2024-03-21 16:41

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("entities", "0021_event"),
        ("corpus", "0045_fragment_provenance"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentEventRelation",
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
                ("notes", models.TextField(blank=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="corpus.document",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="entities.event"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="document",
            name="events",
            field=models.ManyToManyField(
                related_name="documents",
                through="corpus.DocumentEventRelation",
                to="entities.Event",
                verbose_name="Related Events",
            ),
        ),
    ]