import datetime

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

# migration test case adapted from
# https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# and copied from mep-django


class TestMigrations(TransactionTestCase):
    # Base class for migration test case

    # NOTE: subclasses must be marked with @pytest.mark.last
    # to avoid causing errors in fixtures/db state for other tests

    app = None
    migrate_from = None
    migrate_to = None

    def setUp(self):
        assert (
            self.migrate_from and self.migrate_to
        ), "TestCase '{}' must define migrate_from and migrate_to properties".format(
            type(self).__name__
        )
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass


@pytest.mark.last
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


@pytest.mark.last
class AlterSourceEdition(TestMigrations):

    app = "footnotes"
    migrate_from = "0013_add_fields_to_source"
    migrate_to = "0014_alter_source_edition"

    def setUpBeforeMigration(self, apps):
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        source_type = SourceType.objects.create(type="Unknown")
        Source.objects.create(
            title="Book 1", edition="bad data", source_type=source_type
        )
        Source.objects.create(title="Book 2", edition="2", source_type=source_type)
        Source.objects.create(title="Book 3", edition="", source_type=source_type)

    def test_editions_converted_to_int(self):
        Source = self.apps.get_model("footnotes", "Source")
        assert not Source.objects.filter(title="Book 1").first().edition
        assert Source.objects.filter(title="Book 2").first().edition == 2
        assert not Source.objects.filter(title="Book 3").first().edition


@pytest.mark.last
class AlterSourceEditionReverse(TestMigrations):

    app = "footnotes"
    migrate_from = "0014_alter_source_edition"
    migrate_to = "0013_add_fields_to_source"

    def setUpBeforeMigration(self, apps):
        Source = apps.get_model("footnotes", "Source")
        SourceType = apps.get_model("footnotes", "SourceType")
        source_type = SourceType.objects.create(type="Unknown")
        Source.objects.create(title="Book 1", edition=None, source_type=source_type)
        Source.objects.create(title="Book 2", edition=2, source_type=source_type)

    def test_editions_converted_to_string(self):
        Source = self.apps.get_model("footnotes", "Source")
        assert Source.objects.filter(title="Book 1").first().edition == ""
        assert Source.objects.filter(title="Book 2").first().edition == "2"


@pytest.mark.last
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
        source = Source.objects.create(title="Book", source_type=source_type)
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
