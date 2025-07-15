import pytest

from geniza.common.tests import TestMigrations


@pytest.mark.order("last")
@pytest.mark.django_db
class TestDeleteCreditsPageInstances(TestMigrations):
    app = "pages"
    migrate_from = "0007_create_svgimageblock"
    migrate_to = "0008_delete_creditspage_instances"
    credits_page = None

    def setUpBeforeMigration(self, apps):
        # create a Page with content type for CreditsPage
        Page = apps.get_model("wagtailcore", "Page")
        Locale = apps.get_model("wagtailcore", "Locale")
        ContentType = apps.get_model("contenttypes", "ContentType")
        fake_locale = Locale.objects.create()
        (credits_page_type, _) = ContentType.objects.get_or_create(
            app_label="pages", model="creditspage"
        )
        self.credits_page = Page(
            content_type_id=credits_page_type.pk,
            locale_id=fake_locale.pk,
            title="test",
            depth=2,
        )
        self.credits_page.save()

    def test_credits_page_deleted(self):
        # CreditsPage should no longer exist
        Page = self.apps.get_model("wagtailcore", "Page")
        assert not Page.objects.filter(pk=self.credits_page.pk).exists()
