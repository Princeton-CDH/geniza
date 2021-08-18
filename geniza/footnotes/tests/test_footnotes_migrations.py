import datetime

from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
import pytest


# migration test case adapted from
# https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# and copied from mep-django


@pytest.mark.last
class TestMigrations(TransactionTestCase):

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
