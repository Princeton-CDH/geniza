# Generated by Django 3.2.14 on 2022-08-05 17:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0020_alter_footnote_content"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="footnote",
            name="content",
        ),
    ]