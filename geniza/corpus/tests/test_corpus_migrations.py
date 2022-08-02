import pytest

from geniza.common.tests import TestMigrations


@pytest.mark.last
@pytest.mark.django_db
class ReassignLogEntries(TestMigrations):

    app = "corpus"
    migrate_from = "0025_documentprefetchableproxy"
    migrate_to = "0026_delete_documentprefetchableproxy"
    log_entry = None

    def setUpBeforeMigration(self, apps):
        # Create a LogEntry for a Document, assign it to corpus.DocumentPrefetchableProxy ContentType
        LogEntry = apps.get_model("admin", "LogEntry")
        Document = apps.get_model("corpus", "Document")
        ContentType = apps.get_model("contenttypes", "ContentType")
        (document_prefetchable_type, _) = ContentType.objects.get_or_create(
            app_label="corpus", model="documentprefetchableproxy"
        )
        d = Document.objects.create()
        self.log_entry = LogEntry.objects.log_action(
            user_id=1,
            content_type_id=document_prefetchable_type.pk,
            object_id=d.pk,
            object_repr=str(d),
            change_message="created %s" % d,
            action_flag=1,
        )

    def test_log_entries_reassigned(self):
        # LogEntry should be reassigned so that its ContentType is corpus.Document
        ContentType = self.apps.get_model("contenttypes", "ContentType")
        document_type = ContentType.objects.get(app_label="corpus", model="document")
        self.log_entry.refresh_from_db()
        assert self.log_entry.content_type_id == document_type.pk


@pytest.mark.last
@pytest.mark.django_db
class TestConvertSideToSelectedImages(TestMigrations):
    app = "corpus"
    migrate_from = "0032_revise_standard_date_help_text"
    migrate_to = "0033_textblock_selected_images"
    no_side = None
    verso_side = None
    both_sides = None

    def setUpBeforeMigration(self, apps):
        # Create 3 TextBlocks, set sides
        TextBlock = apps.get_model("corpus", "TextBlock")
        Document = apps.get_model("corpus", "Document")
        Fragment = apps.get_model("corpus", "Fragment")
        doc = Document.objects.create()
        frag = Fragment.objects.create()
        self.no_side = TextBlock.objects.create(side="", document=doc, fragment=frag)
        self.verso_side = TextBlock.objects.create(
            side="v", document=doc, fragment=frag
        )
        self.both_sides = TextBlock.objects.create(
            side="rv", document=doc, fragment=frag
        )

    def test_sides_converted(self):
        TextBlock = self.apps.get_model("corpus", "TextBlock")
        # should set selected images to [] for no side, [1] for verso, [0, 1] for recto/verso
        no_side = TextBlock.objects.get(pk=self.no_side.pk)
        assert len(no_side.selected_images) == 0
        verso_side = TextBlock.objects.get(pk=self.verso_side.pk)
        assert len(verso_side.selected_images) == 1
        assert verso_side.selected_images[0] == 1  # verso = img index 1
        both_sides = TextBlock.objects.get(pk=self.both_sides.pk)
        assert len(both_sides.selected_images) == 2
        assert 0 in both_sides.selected_images and 1 in both_sides.selected_images


@pytest.mark.last
@pytest.mark.django_db
class TestConvertSelectedImagesToSide(TestMigrations):
    app = "corpus"
    migrate_from = "0033_textblock_selected_images"
    migrate_to = "0032_revise_standard_date_help_text"
    no_side = None
    verso_side = None
    both_sides = None

    def setUpBeforeMigration(self, apps):
        # Create 3 TextBlocks, set selected images
        TextBlock = apps.get_model("corpus", "TextBlock")
        Document = apps.get_model("corpus", "Document")
        Fragment = apps.get_model("corpus", "Fragment")
        doc = Document.objects.create()
        frag = Fragment.objects.create()
        self.no_side = TextBlock.objects.create(
            selected_images=[], document=doc, fragment=frag
        )
        self.verso_side = TextBlock.objects.create(
            selected_images=[1], document=doc, fragment=frag
        )
        self.both_sides = TextBlock.objects.create(
            selected_images=[0, 1], document=doc, fragment=frag
        )

    def test_sides_converted(self):
        TextBlock = self.apps.get_model("corpus", "TextBlock")
        # should set side to empty for no selected images, v for verso, rv for recto/verso
        no_side = TextBlock.objects.get(pk=self.no_side.pk)
        assert no_side.side == ""
        verso_side = TextBlock.objects.get(pk=self.verso_side.pk)
        assert verso_side.side == "v"
        both_sides = TextBlock.objects.get(pk=self.both_sides.pk)
        assert both_sides.side == "rv"
