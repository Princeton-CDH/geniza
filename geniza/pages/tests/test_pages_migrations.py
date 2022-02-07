import pytest
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

    def test_page_converted(self):
        ContentPage = self.apps.get_model("pages", "ContentPage")
        for page in ContentPage.objects.all():
            assert page.body.raw_text is None
            assert len(page.body) == 1
            assert page.body[0].block_type == "paragraph"


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
        content_page.body = [("paragraph", RichText(RAW_TEXT))]
        content_page.save()

    def test_page_converted(self):
        ContentPage = self.apps.get_model("pages", "ContentPage")
        for page in ContentPage.objects.all():
            assert isinstance(page.body, str)
