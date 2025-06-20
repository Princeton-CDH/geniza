# Generated by Django 3.2.23 on 2025-02-04 19:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("footnotes", "0032_alter_footnote_content_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="footnote",
            name="emendations",
            field=models.CharField(
                blank=True,
                help_text="Displays publicly. For minor emendations to a transcription or translation (not including typo corrections), enter Your Name, Year. May include multiple names and dates. For significant alterations to a transcription or translation, create a new source indicating co-authorship.",
                max_length=512,
                null=True,
                verbose_name="minor emendations by",
            ),
        ),
        migrations.AlterField(
            model_name="footnote",
            name="notes",
            field=models.TextField(
                blank=True,
                help_text="Additional context. Only visible to admins/editors.",
            ),
        ),
    ]
