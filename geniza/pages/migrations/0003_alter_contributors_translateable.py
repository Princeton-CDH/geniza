# Generated by Django 3.2.8 on 2021-12-17 16:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0002_create_contributor_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="contributor",
            name="first_name_ar",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="first_name_en",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="first_name_he",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="last_name_ar",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="last_name_en",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="last_name_he",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="role_ar",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="role_en",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="contributor",
            name="role_he",
            field=models.CharField(max_length=255, null=True),
        ),
    ]
