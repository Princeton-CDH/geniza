# Generated by Django 3.2.23 on 2024-03-05 21:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("corpus", "0044_populate_fragment_old_shelfmark"),
    ]

    operations = [
        migrations.AddField(
            model_name="fragment",
            name="provenance",
            field=models.TextField(
                blank=True,
                help_text="The origin and acquisition history of this fragment.",
            ),
        ),
    ]