import django.db.models.deletion
from django.contrib.auth.management import create_permissions
from django.db import migrations, models

CONTENT_EDITOR = "Content Editor"
CONTENT_ADMIN = "Content Admin"
docevent_perms = [
    "add_documenteventrelation",
    "change_documenteventrelation",
    "delete_documenteventrelation",
    "view_documenteventrelation",
]


class CreateModelIfMissing(migrations.CreateModel):
    """Create the table only if it does not already exist; existing databases
    have it from corpus migration 0046, before the model moved to entities."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.name)
        tables = schema_editor.connection.introspection.table_names()
        if model._meta.db_table not in tables:
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # never drop the table on rollback
        pass


def move_contenttype(apps, schema_editor):
    # keep permissions and admin log entries attached to the moved model
    ContentType = apps.get_model("contenttypes", "ContentType")
    if not ContentType.objects.filter(
        app_label="entities", model="documenteventrelation"
    ).exists():
        ContentType.objects.filter(
            app_label="corpus", model="documenteventrelation"
        ).update(app_label="entities")


def set_docevent_permissions(apps, schema_editor):
    # previously assigned in 0022_event_permissions; on fresh databases the
    # model does not exist until this migration, so assign permissions here
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    permissions = Permission.objects.filter(
        content_type__app_label="entities", codename__in=docevent_perms
    )
    for group in Group.objects.filter(name__in=[CONTENT_EDITOR, CONTENT_ADMIN]):
        group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("corpus", "0053_alter_document_doc_date_standard"),
        ("entities", "0036_alter_person_description_alter_person_description_ar_and_more"),
    ]

    operations = [
        CreateModelIfMissing(
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
                        on_delete=django.db.models.deletion.CASCADE,
                        to="entities.event",
                    ),
                ),
            ],
            options={
                "db_table": "corpus_documenteventrelation",
            },
        ),
        migrations.AddField(
            model_name="event",
            name="documents",
            field=models.ManyToManyField(
                related_name="events",
                through="entities.DocumentEventRelation",
                to="corpus.document",
                verbose_name="Related Documents",
            ),
        ),
        migrations.RunPython(move_contenttype, migrations.RunPython.noop),
        migrations.RunPython(set_docevent_permissions, migrations.RunPython.noop),
    ]
