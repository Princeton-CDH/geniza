import pytest

from geniza.common.tests import TestMigrations


@pytest.mark.order("last")
class MergeIndiaBookSources(TestMigrations):
    app = "footnotes"
    migrate_from = "0011_split_goitein_typedtexts"
    migrate_to = "0012_merge_indiabook_sources"

    def setUpBeforeMigration(self, apps):
        ContentType = apps.get_model("contenttypes", "ContentType")
        Footnote = apps.get_model("footnotes", "Footnote")
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")

        ctype = ContentType.objects.get(model="sourcetype")
        source_type = SourceType.objects.create(type="Unknown")
        indiabk1 = Source.objects.create(title="India Book 1", source_type=source_type)
        indiabk1a = Source.objects.create(title="India Book 1", source_type=source_type)
        # content object is required for a footnote, but for this test
        # we don't care what it is; just use source type object
        fn1 = Footnote.objects.create(
            source=indiabk1, content_type=ctype, object_id=source_type.pk
        )
        fn2 = Footnote.objects.create(
            source=indiabk1a, content_type=ctype, object_id=source_type.pk
        )

    def test_sources_merged(self):
        Footnote = self.apps.get_model("footnotes", "Footnote")
        Source = self.apps.get_model("footnotes", "Source")

        assert Source.objects.count() == 1
        assert Footnote.objects.count() == 2


@pytest.mark.order("last")
class AlterSourceEdition(TestMigrations):
    app = "footnotes"
    migrate_from = "0013_add_fields_to_source"
    migrate_to = "0014_alter_source_edition"

    src1 = None
    src2 = None
    src3 = None

    def setUpBeforeMigration(self, apps):
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        source_type = SourceType.objects.create(type="Unknown")
        self.src1 = Source.objects.create(
            title_en="Book 1", edition="bad data", source_type=source_type
        )
        self.src2 = Source.objects.create(
            title_en="Book 2", edition="2", source_type=source_type
        )
        self.src3 = Source.objects.create(
            title_en="Book 3", edition="", source_type=source_type
        )

    def test_editions_converted_to_int(self):
        self.src1.refresh_from_db()
        assert not self.src1.edition
        self.src2.refresh_from_db()
        assert self.src2.edition == 2
        self.src3.refresh_from_db()
        assert not self.src3.edition


@pytest.mark.order("last")
class AlterSourceEditionReverse(TestMigrations):
    app = "footnotes"
    migrate_from = "0014_alter_source_edition"
    migrate_to = "0013_add_fields_to_source"

    src1 = None
    src2 = None

    def setUpBeforeMigration(self, apps):
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        source_type = SourceType.objects.create(type="Unknown")
        self.src1 = Source.objects.create(
            title_en="Book 1", edition=None, source_type=source_type
        )
        self.src2 = Source.objects.create(
            title_en="Book 2", edition=2, source_type=source_type
        )

    def test_editions_converted_to_string(self):
        self.src1.refresh_from_db()
        assert self.src1.edition == ""
        self.src2.refresh_from_db()
        assert self.src2.edition == "2"


@pytest.mark.order("last")
class TestFootnoteLocationPpMigration(TestMigrations):
    app = "footnotes"
    migrate_from = "0014_alter_source_edition"
    migrate_to = "0015_add_footnote_location_pp"

    def setUpBeforeMigration(self, apps):
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        Footnote = apps.get_model("footnotes", "Footnote")
        ContentType = apps.get_model("contenttypes", "ContentType")

        source_type = SourceType.objects.create(type="Unknown")
        source = Source.objects.create(title_en="Book", source_type=source_type)
        source_ctype = ContentType.objects.get(
            app_label="footnotes", model="sourcetype"
        )

        # footnotes require a content object; use source type object as a stand-in
        fn_opts = {
            "source": source,
            "object_id": source_type.pk,
            "content_type": source_ctype,
        }

        # create footnotes with a variety of locations to update
        Footnote.objects.bulk_create(
            [
                # single page
                Footnote(location="5", **fn_opts),
                Footnote(location="74", **fn_opts),
                # page ranges (presumed)
                Footnote(location="55-74", **fn_opts),
                Footnote(location="23ff.", **fn_opts),
                Footnote(location="44, doc 3", **fn_opts),
                # don't prefix these
                Footnote(location="49ב", **fn_opts),
                Footnote(location="doc 5", **fn_opts),
            ]
        )

    def test_locations_prefixed_pp(self):
        Footnote = self.apps.get_model("footnotes", "Footnote")
        # check for locations we expect to be modified / unmodified
        # - single page
        for page_loc in ["5", "74"]:
            assert Footnote.objects.filter(location="p. %s" % page_loc).exists()
        # - page range
        for page_loc in ["55-74", "23ff.", "44, doc 3"]:
            assert Footnote.objects.filter(location="pp. %s" % page_loc).exists()
        # unmodified
        for page_loc in ["doc 5", "49ב"]:
            assert Footnote.objects.filter(location=page_loc).exists()


@pytest.mark.order("last")
class TestRenameTypedTextsMigration(TestMigrations):
    app = "footnotes"
    migrate_from = "0015_add_footnote_location_pp"
    migrate_to = "0016_rename_typed_texts"
    typed_texts_source = None
    other_source = None

    def setUpBeforeMigration(self, apps):
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        source_type = SourceType.objects.create(type="Unknown")
        typed_texts_source = Source.objects.create(
            title_en="typed texts", source_type=source_type
        )
        self.typed_texts_source = typed_texts_source
        other_source = Source.objects.create(
            title_en="other title", source_type=source_type
        )
        self.other_source = other_source

    def test_rename_typed_texts(self):
        # should rename "typed texts" (only) to "unpublished editions"
        self.typed_texts_source.refresh_from_db()
        assert self.typed_texts_source.title_en == "unpublished editions"
        self.other_source.refresh_from_db()
        assert self.other_source.title_en == "other title"

        LogEntry = self.apps.get_model("admin", "LogEntry")
        msg = 'changed title "typed texts" to "unpublished editions"'
        # should create log entries with appropriate message for typed texts, but not other source
        assert (
            LogEntry.objects.filter(
                change_message=msg, object_id=self.typed_texts_source.pk
            ).count()
            == 1
        )
        assert (
            LogEntry.objects.filter(
                change_message=msg, object_id=self.other_source.pk
            ).count()
            == 0
        )


@pytest.mark.order("last")
@pytest.mark.django_db
class TestDigitalFootnoteLocation(TestMigrations):
    app = "footnotes"
    migrate_from = "0029_source_help_text"
    migrate_to = "0030_digital_footnote_location"
    digital_edition = None
    digital_translation = None

    def setUpBeforeMigration(self, apps):
        Footnote = apps.get_model("footnotes", "Footnote")
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        ContentType = apps.get_model("contenttypes", "ContentType")
        Document = apps.get_model("corpus", "Document")
        document_contenttype = ContentType.objects.get_for_model(Document)

        book = SourceType.objects.create(type="Book")
        source = Source.objects.create(source_type=book)
        source_2 = Source.objects.create(source_type=book)

        # example where there is 1 corresponding footnote with location
        Footnote.objects.create(
            source=source,
            doc_relation=["E"],  # Footnote.EDITION
            object_id=123454321,
            content_type=document_contenttype,
            location="doc. 123",
        )
        self.digital_edition = Footnote.objects.create(
            source=source,
            doc_relation=["X"],  # Footnote.DIGITAL_EDITION
            object_id=123454321,
            content_type=document_contenttype,
        )

        # example where there are 2 corresponding footnotes with location
        Footnote.objects.create(
            source=source_2,
            doc_relation=["T"],  # Footnote.TRANSLATION
            object_id=123454321,
            content_type=document_contenttype,
            location="doc. 1234",
        )
        Footnote.objects.create(
            source=source_2,
            doc_relation=["T"],  # Footnote.TRANSLATION
            object_id=123454321,
            content_type=document_contenttype,
            location="doc. 123454321",
        )
        self.digital_translation = Footnote.objects.create(
            source=source,
            doc_relation=["Y"],  # Footnote.DIGITAL_TRANSLATION
            object_id=123454321,
            content_type=document_contenttype,
        )

    def test_migrate_footnote_locations(self):
        # should have copied the edition's location to the digital edition
        self.digital_edition.refresh_from_db()
        assert self.digital_edition.location == "doc. 123"

        # should NOT have copied the translation's location becasue there are multiple
        # corresponding translation footnotes
        self.digital_translation.refresh_from_db()
        assert self.digital_translation.location == ""


@pytest.mark.order("last")
@pytest.mark.django_db
class TestPopulateFootnoteEmendations(TestMigrations):
    app = "footnotes"
    migrate_from = "0033_footnote_emendations"
    migrate_to = "0034_populate_footnote_emendations"
    footnote_undated_emendations = None
    footnote_emendations = None
    footnote_2_emenders = None
    footnote_2_emenders_alt = None
    name_1 = "Alan Elbaum"
    date_1 = "2020"
    name_2 = "Marina Rustow"
    date_2 = "2023"

    def setUpBeforeMigration(self, apps):
        Footnote = apps.get_model("footnotes", "Footnote")
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        ContentType = apps.get_model("contenttypes", "ContentType")
        Document = apps.get_model("corpus", "Document")
        document_contenttype = ContentType.objects.get_for_model(Document)

        book = SourceType.objects.create(type="Book")
        source = Source.objects.create(source_type=book)

        # undated emendations
        self.footnote_undated_emendations = Footnote.objects.create(
            source=source,
            doc_relation=["X"],
            object_id=12345432,
            content_type=document_contenttype,
            notes=f"With emendations by {self.name_2}.",
        )

        # example where there is a person and date listed for emendations
        self.footnote_emendations = Footnote.objects.create(
            source=source,
            doc_relation=["X"],
            object_id=12345433,
            content_type=document_contenttype,
            notes=f"With emendations by {self.name_1} ({self.date_1}).",
        )

        # examples where there are 2 people listed for emendations
        self.footnote_2_emenders = Footnote.objects.create(
            source=source,
            doc_relation=["X"],
            object_id=12345434,
            content_type=document_contenttype,
            notes=f"with emendations by {self.name_1} ({self.date_1}), and {self.name_2} ({self.date_2}).",
        )
        self.footnote_2_emenders_alt = Footnote.objects.create(
            source=source,
            doc_relation=["X"],
            object_id=12345435,
            content_type=document_contenttype,
            notes=f"With emendations by {self.name_1} ({self.date_1}) and {self.name_2} ({self.date_2}).",
        )

    def test_populate_footnote_emendations(self):
        # no emendations in notes: no emendations field content
        self.footnote_undated_emendations.refresh_from_db()
        assert not self.footnote_undated_emendations.emendations

        # dated emendations in notes: should format correctly
        self.footnote_emendations.refresh_from_db()
        assert self.footnote_emendations.emendations == f"{self.name_1}, {self.date_1}"

        # dated emendations by two people in notes: should format correctly
        self.footnote_2_emenders.refresh_from_db()
        assert (
            self.footnote_2_emenders.emendations
            == f"{self.name_1}, {self.date_1} and {self.name_2}, {self.date_2}"
        )
        self.footnote_2_emenders_alt.refresh_from_db()
        assert (
            self.footnote_2_emenders_alt.emendations
            == f"{self.name_1}, {self.date_1} and {self.name_2}, {self.date_2}"
        )
