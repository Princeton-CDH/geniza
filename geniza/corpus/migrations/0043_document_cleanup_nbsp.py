# Generated by Django 3.2.16 on 2023-10-20 18:51
import re

from django.db import migrations


def cleanup_document_nbsp(apps, schema_editor):
    """Cleanup all documents with unicode nbsp in their descriptions"""
    Document = apps.get_model("corpus", "Document")
    for doc in Document.objects.filter(description_en__icontains="\xa0"):
        doc.description_en = re.sub(r"[\xa0 ]+", " ", doc.description_en)
        doc.save()


class Migration(migrations.Migration):
    dependencies = [
        ("corpus", "0042_document_image_overrides"),
    ]

    operations = [
        migrations.RunPython(
            cleanup_document_nbsp, reverse_code=migrations.RunPython.noop
        )
    ]
