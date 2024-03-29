# Generated by Django 3.2.13 on 2022-09-16 12:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0021_footnote_add_digital_edition_rel"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="footnote",
            constraint=models.UniqueConstraint(
                condition=models.Q(("doc_relation__contains", "X")),
                fields=("source", "object_id", "content_type", "doc_relation"),
                name="one_digital_edition_per_document_and_source",
            ),
        ),
    ]
