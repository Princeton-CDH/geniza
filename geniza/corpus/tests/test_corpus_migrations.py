import os

import pytest
from django.conf import settings

from geniza.common.tests import TestMigrations


@pytest.mark.order("last")
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
        User = apps.get_model("auth", "User")
        (document_prefetchable_type, _) = ContentType.objects.get_or_create(
            app_label="corpus", model="documentprefetchableproxy"
        )
        d = Document.objects.create()
        (user, _) = User.objects.get_or_create(username=settings.SCRIPT_USERNAME)
        self.log_entry = LogEntry.objects.log_action(
            user_id=user.pk,
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


@pytest.mark.order("last")
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


@pytest.mark.order("last")
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


@pytest.mark.order("last")
@pytest.mark.django_db
class TestMergeDuplicateTags(TestMigrations):
    app = "corpus"
    migrate_from = "0033_textblock_selected_images"
    migrate_to = "0034_merge_duplicate_tags"
    doc1 = None
    doc2 = None
    doc3 = None

    def setUpBeforeMigration(self, apps):
        ContentType = apps.get_model("contenttypes", "ContentType")
        Document = apps.get_model("corpus", "Document")
        Tag = apps.get_model("taggit", "Tag")
        TaggedItem = apps.get_model("taggit", "TaggedItem")
        User = apps.get_model("auth", "User")
        doc_contenttype = ContentType.objects.get(app_label="corpus", model="document")

        self.doc1 = Document.objects.create()
        self.doc2 = Document.objects.create()
        self.doc3 = Document.objects.create()
        goodtag, _ = Tag.objects.get_or_create(name="example", slug="example")
        badtag1, _ = Tag.objects.get_or_create(name="Exämple", slug="example_1")
        badtag2, _ = Tag.objects.get_or_create(name="éxample", slug="example_2")
        badtag3, _ = Tag.objects.get_or_create(
            name="Ḥalfon b. Menashshe", slug="halfon_b_menashshe"
        )
        TaggedItem.objects.get_or_create(
            tag=goodtag,
            content_type=doc_contenttype,
            object_id=self.doc1.pk,
        )
        TaggedItem.objects.get_or_create(
            tag=badtag1,
            content_type=doc_contenttype,
            object_id=self.doc2.pk,
        )
        TaggedItem.objects.get_or_create(
            tag=badtag2,  # doc2 will have two variants of this tag collapsed into one
            content_type=doc_contenttype,
            object_id=self.doc2.pk,
        )
        TaggedItem.objects.get_or_create(
            tag=badtag2,
            content_type=doc_contenttype,
            object_id=self.doc3.pk,
        )
        TaggedItem.objects.get_or_create(
            tag=badtag3,
            content_type=doc_contenttype,
            object_id=self.doc3.pk,
        )

        # ensure script user exists
        User.objects.get_or_create(username=settings.SCRIPT_USERNAME)

    def test_tags_merged(self):
        ContentType = self.apps.get_model("contenttypes", "ContentType")
        LogEntry = self.apps.get_model("admin", "LogEntry")
        Tag = self.apps.get_model("taggit", "Tag")
        TaggedItem = self.apps.get_model("taggit", "TaggedItem")
        doc_contenttype = ContentType.objects.get(app_label="corpus", model="document")
        tag_contenttype = ContentType.objects.get(app_label="taggit", model="tag")

        # bad tags should be deleted
        assert not Tag.objects.filter(name="Exämple").exists()
        assert not Tag.objects.filter(name="éxample").exists()
        assert not Tag.objects.filter(name="Ḥalfon b. Menashshe").exists()

        # TaggedItems with any of the bad tags should also be deleted
        assert not TaggedItem.objects.filter(tag__name="Exämple").exists()
        assert not TaggedItem.objects.filter(tag__name="éxample").exists()
        assert not TaggedItem.objects.filter(tag__name="Ḥalfon b. Menashshe").exists()

        # should have all three documents tagged with "Example", and one tagged with "Halfon b. Menashshe"

        assert TaggedItem.objects.filter(tag__name="Example").count() == 3
        assert TaggedItem.objects.filter(tag__name="Halfon b. Menashshe").count() == 1

        # doc2 should only have one tag, despite being tagged with two variants of "example"
        assert (
            TaggedItem.objects.filter(
                content_type=doc_contenttype, object_id=self.doc2.pk
            ).count()
            == 1
        )

        # should create a log entry for tag rename
        assert LogEntry.objects.filter(
            content_type_id=tag_contenttype.pk, change_message="Removed diacritics"
        ).exists()

        # should create a log entry for tag merge
        assert LogEntry.objects.filter(
            content_type_id=tag_contenttype.pk,
            change_message="Merged example, éxample; removed diacritics",
        ).exists()


@pytest.mark.order("last")
@pytest.mark.django_db
class TestMergeJTSENACollections(TestMigrations):
    app = "corpus"
    migrate_from = "0035_document_image_order_override"
    migrate_to = "0036_collections_merge_jts_ena"
    jts_collection = None
    ena_fragment = None
    jts_fragment = None

    def setUpBeforeMigration(self, apps):
        Collection = apps.get_model("corpus", "Collection")
        (self.jts_collection, _) = Collection.objects.get_or_create(
            library="Jewish Theological Seminary Library",
            lib_abbrev="JTS",
            location="New York",
        )
        (ena, _) = Collection.objects.get_or_create(
            library="Jewish Theological Seminary Library",
            lib_abbrev="JTS",
            abbrev="ENA",
            name="Elkan Nathan Adler",
            location="New York",
        )
        # create one ENA and one JTS fragment
        Fragment = apps.get_model("corpus", "Fragment")
        self.ena_fragment = Fragment.objects.create(
            shelfmark="ENA 1",
            collection=ena,
        )
        self.jts_fragment = Fragment.objects.create(
            shelfmark="JTS 1",
            collection=self.jts_collection,
        )

    def test_merged(self):
        Collection = self.apps.get_model("corpus", "Collection")
        Fragment = self.apps.get_model("corpus", "Fragment")
        # there should no longer be an ENA collection
        assert not Collection.objects.filter(abbrev="ENA").exists()
        # both fragments' collections should be JTS
        jts_fragment = Fragment.objects.get(pk=self.jts_fragment.pk)
        assert jts_fragment.collection.pk == self.jts_collection.pk
        ena_fragment = Fragment.objects.get(pk=self.ena_fragment.pk)
        assert ena_fragment.collection.pk == self.jts_collection.pk


@pytest.mark.order("second_to_last")
@pytest.mark.django_db
class TestDocumentImageOverrides(TestMigrations):
    app = "corpus"
    migrate_from = "0041_dating_rationale"
    migrate_to = "0042_document_image_overrides"
    no_override = None
    order_override = None

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("corpus", "Document")
        self.no_override = Document.objects.create()
        self.order_override = Document.objects.create(
            image_order_override=["canvas2", "canvas1"]
        )

    def test_image_order_to_json(self):
        Document = self.apps.get_model("corpus", "Document")
        no_override = Document.objects.get(pk=self.no_override.pk)
        assert no_override.image_overrides == {}
        order_override = Document.objects.get(pk=self.order_override.pk)
        assert order_override.image_overrides["canvas2"]["order"] == 0
        assert order_override.image_overrides["canvas1"]["order"] == 1


@pytest.mark.order("second_to_last")
@pytest.mark.django_db
class TestDocumentImageOverridesReverse(TestMigrations):
    app = "corpus"
    migrate_from = "0042_document_image_overrides"
    migrate_to = "0041_dating_rationale"
    no_override = None
    order_override = None

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("corpus", "Document")
        self.no_override = Document.objects.create()
        self.order_override = Document.objects.create(
            image_overrides={
                "canvas1": {"order": 1},
                "canvas2": {"order": 0},
            }
        )

    def test_image_overrides_to_order_array(self):
        Document = self.apps.get_model("corpus", "Document")
        no_override = Document.objects.get(pk=self.no_override.pk)
        assert not no_override.image_order_override
        order_override = Document.objects.get(pk=self.order_override.pk)
        assert order_override.image_order_override == ["canvas2", "canvas1"]


@pytest.mark.order("second_to_last")
@pytest.mark.django_db
class TestDocumentCleanupNbsp(TestMigrations):
    app = "corpus"
    migrate_from = "0042_document_image_overrides"
    migrate_to = "0043_document_cleanup_nbsp"
    document = None

    def setUpBeforeMigration(self, apps):
        Document = apps.get_model("corpus", "Document")
        self.document = Document.objects.create(
            description_en="Example\xa0with that\xa0space"
        )

    def test_cleanup_nbsp(self):
        self.document.refresh_from_db()
        assert "\xa0" not in self.document.description_en
        assert self.document.description_en == "Example with that space"
