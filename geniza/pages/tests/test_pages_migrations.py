import json
from datetime import datetime

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from wagtail.core.rich_text import RichText

from geniza.common.tests import TestMigrations

RAW_TEXT = "<h2>Geniza Project contributors</h2><h3>Co-PI Research Lead</h3><p><b>Marina Rustow</b></p<h3>Co-PI Technical Lead</h3><p>Rebecca Sutton Koeser</p><blockquote>Project Manager (March 2020-Present)</blockquote><blockquote>Rachel Richman</blockquote>"


@pytest.mark.last
@pytest.mark.django_db
class TestConvertFieldsToStreamField(TestMigrations):

    app = "pages"
    migrate_from = "0005_containerpage"
    migrate_to = "0006_convert_richtextfield_to_streamfield"

    def setUpBeforeMigration(self, apps):
        # create a ContentPage with some rich text content
        ContentPage = apps.get_model("pages", "ContentPage")
        ContentType = apps.get_model("contenttypes", "ContentType")
        Locale = apps.get_model("wagtailcore", "Locale")
        fake_locale = Locale.objects.create()
        (content_page_type, _) = ContentType.objects.get_or_create(
            app_label="pages", model="ContentPage"
        )
        content_page = ContentPage(
            title="Credits",
            depth=2,
            content_type_id=content_page_type.pk,
            locale_id=fake_locale.pk,
        )
        content_page.body = RAW_TEXT
        content_page.save()

        # create a revision with slightly different content
        content_page.revisions.create(
            created_at=datetime(year=2022, month=2, day=7),
            content_json=json.dumps(
                {"body": RAW_TEXT + "<p>test</p>"}, cls=DjangoJSONEncoder
            ),
        )
        # create a revision with nested (StreamField, i.e. post-conversion) JSON
        body_list = json.dumps(
            [{"value": {"paragraph": RAW_TEXT + "<p>test</p>"}, "type": "paragraph"}]
        )
        content_page.revisions.create(
            created_at=datetime(year=2022, month=2, day=7),
            content_json=json.dumps({"body": body_list}, cls=DjangoJSONEncoder),
        )

    def test_page_converted(self):
        # Test ContentPage converted to StreamField
        ContentPage = self.apps.get_model("pages", "ContentPage")
        for page in ContentPage.objects.all():
            # should not have raw text
            assert page.body.raw_text is None
            if page.body:
                # should convert all body text into length 1 lists
                assert len(page.body) == 1
                # first element should be a paragraph block
                assert page.body[0].block_type == "paragraph"

    def test_revision_converted(self):
        # Test revisions converted to appropriate JSON for StreamField
        ContentPage = self.apps.get_model("pages", "ContentPage")
        for page in ContentPage.objects.all():
            for rev in page.revisions.all():
                revision_data = json.loads(rev.content_json)
                body = revision_data.get("body")
                # json load should not throw ValueError, because "body" should now be valid json
                body_data = json.loads(body)
                # should be a list of stream field blocks
                assert isinstance(body_data, list)


@pytest.mark.last
@pytest.mark.django_db
class TestConvertFieldsReverseToRichTextField(TestMigrations):

    app = "pages"
    migrate_from = "0006_convert_richtextfield_to_streamfield"
    migrate_to = "0005_containerpage"

    def setUpBeforeMigration(self, apps):
        # create a ContentPage with some rich text content
        ContentPage = apps.get_model("pages", "ContentPage")
        ContentType = apps.get_model("contenttypes", "ContentType")
        Locale = apps.get_model("wagtailcore", "Locale")
        fake_locale = Locale.objects.create()
        (content_page_type, _) = ContentType.objects.get_or_create(
            app_label="pages", model="ContentPage"
        )
        content_page = ContentPage(
            title="Credits",
            depth=2,
            content_type_id=content_page_type.pk,
            locale_id=fake_locale.pk,
        )
        # body is list of blocks
        content_page.body = [("paragraph", RichText(RAW_TEXT))]
        content_page.save()

        # create a revision with slightly different content
        content_page.revisions.create(
            created_at=datetime(year=2022, month=2, day=7),
            content_json=json.dumps(
                {"body": RAW_TEXT + "<p>test</p>"}, cls=DjangoJSONEncoder
            ),
        )
        # create a revision with nested (StreamField, i.e. post-conversion) JSON
        body_list = json.dumps(
            [{"value": {"paragraph": RAW_TEXT + "<p>test</p>"}, "type": "paragraph"}]
        )
        content_page.revisions.create(
            created_at=datetime(year=2022, month=2, day=7),
            content_json=json.dumps({"body": body_list}, cls=DjangoJSONEncoder),
        )

    def test_page_converted(self):
        # Test ContentPage converted to RichTextField
        ContentPage = self.apps.get_model("pages", "ContentPage")
        for page in ContentPage.objects.all():
            # Should now be string, not list of blocks
            assert isinstance(page.body, str)

    def test_revision_converted(self):
        # Test revisions converted to appropriate JSON for RichTextField
        ContentPage = self.apps.get_model("pages", "ContentPage")
        for page in ContentPage.objects.all():
            for rev in page.revisions.all():
                revision_data = json.loads(rev.content_json)
                body = revision_data.get("body")
                # body should now be a string containing the page content raw text
                assert isinstance(body, str)
