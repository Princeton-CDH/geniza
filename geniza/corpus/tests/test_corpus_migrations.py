import pytest

from geniza.common.tests import TestMigrations


@pytest.mark.last
@pytest.mark.django_db
class ReassignLogEntries(TestMigrations):

    app = "corpus"
    migrate_from = "0025_documentprefetchableproxy"
    migrate_to = "0026_delete_documentprefetchableproxy"

    def setUpBeforeMigration(self, apps):
        # Create a LogEntry for a Document, assign it to corpus.DocumentPrefetchableProxy ContentType
        LogEntry = apps.get_model("admin", "LogEntry")
        Document = apps.get_model("corpus", "Document")
        ContentType = apps.get_model("contenttypes", "ContentType")
        (document_prefetchable_type, _) = ContentType.objects.get_or_create(
            app_label="corpus", model="documentprefetchableproxy"
        )
        d = Document.objects.create()
        LogEntry.objects.log_action(
            user_id=1,
            content_type_id=document_prefetchable_type.pk,
            object_id=d.pk,
            object_repr=str(d),
            change_message="created %s" % d,
            action_flag=1,
        )

    def test_log_entries_reassigned(self):
        # LogEntry should be reassigned so that its ContentType is corpus.Document
        LogEntry = self.apps.get_model("admin", "LogEntry")
        ContentType = self.apps.get_model("contenttypes", "ContentType")
        document_type = ContentType.objects.get(app_label="corpus", model="document")
        log_entry = LogEntry.objects.first()
        assert log_entry.content_type_id == document_type.pk
