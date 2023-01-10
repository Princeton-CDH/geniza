import pytest
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from geniza.common.tests import TestMigrations
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source, SourceType


@pytest.mark.last
@pytest.mark.django_db
class TestAssociateRelatedFootnotes(TestMigrations):
    app = "annotations"
    migrate_from = "0002_annotation_footnote"
    migrate_to = "0003_associate_related_footnotes"
    annotation = None
    anno_no_footnote_match = None
    footnote = None

    def setUpBeforeMigration(self, apps):
        Annotation = apps.get_model("annotations", "Annotation")
        User = apps.get_model("auth", "User")
        book = SourceType.objects.create(type="Book")
        source = Source.objects.create(source_type=book)
        doc = Document.objects.create()
        document_contenttype = ContentType.objects.get_for_model(Document)
        self.footnote = Footnote.objects.create(
            source=source,
            doc_relation=["X"],
            object_id=doc.pk,
            content_type=document_contenttype,
        )
        self.annotation = Annotation.objects.create(
            content={
                "body": [{"value": "Test annotation"}],
                "target": {
                    "source": {
                        "id": "http://ex.co/iiif/canvas/1",
                        "partOf": {"id": doc.manifest_uri},
                    }
                },
                "dc:source": source.uri,
            },
        )
        source_2 = Source.objects.create(source_type=book)
        self.anno_no_footnote_match = Annotation.objects.create(
            content={
                "body": [{"value": "Annotation 2"}],
                "target": {
                    "source": {
                        "id": "http://ex.co/iiif/canvas/2",
                        "partOf": {"id": doc.manifest_uri},
                    }
                },
                "dc:source": source_2.uri,
            },
        )

        # ensure script user exists
        User.objects.get_or_create(username=settings.SCRIPT_USERNAME)

    def test_footnote_associated(self):
        # should associate self.footnote with self.annotation
        Annotation = self.apps.get_model("annotations", "Annotation")
        annotation = Annotation.objects.get(pk=self.annotation.pk)
        assert annotation.footnote.pk == self.footnote.pk

        # should remove manifest and source URIs from annotation content
        assert not "partOf" in annotation.content["target"]["source"]
        assert not "dc:source" in annotation.content

    def test_footnote_created(self):
        # should create a footnote and a log entry when there is no matching footnote
        Annotation = self.apps.get_model("annotations", "Annotation")
        LogEntry = self.apps.get_model("admin", "LogEntry")
        anno_no_footnote_match = Annotation.objects.get(
            pk=self.anno_no_footnote_match.pk
        )
        # new footnote exists
        assert Footnote.objects.filter(pk=anno_no_footnote_match.footnote.pk).exists()
        # log entry created
        assert LogEntry.objects.filter(
            content_type_id=ContentType.objects.get_for_model(Footnote).pk,
            change_message="Footnote automatically created via annotation migration.",
            object_id=anno_no_footnote_match.footnote.pk,
        ).exists()
