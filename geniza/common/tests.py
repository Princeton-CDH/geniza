from doctest import testmod
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponseRedirect
from django.test import TestCase, TransactionTestCase, override_settings

from geniza.common.admin import LocalUserAdmin, custom_empty_field_list_filter
from geniza.common.fields import NaturalSortField, RangeField, RangeWidget
from geniza.common.middleware import PublicLocaleMiddleware
from geniza.common.utils import absolutize_url, custom_tag_string


@pytest.mark.django_db
class TestLocalUserAdmin(TestCase):
    def test_group_names(self):
        testuser = User.objects.create(username="test")
        local_useradm = LocalUserAdmin(User, "")

        assert local_useradm.group_names(testuser) is None

        grp1 = Group.objects.create(name="testers")
        grp2 = Group.objects.create(name="staff")
        grp3 = Group.objects.create(name="superusers")

        testuser.groups.add(grp1, grp2)
        group_names = local_useradm.group_names(testuser)
        assert grp1.name in group_names
        assert grp2.name in group_names
        assert grp3.name not in group_names


class TestCommonUtils(TestCase):
    @pytest.mark.django_db
    def test_absolutize_url(self):
        # Borrowed from https://github.com/Princeton-CDH/mep-django/blob/main/mep/common/tests.py
        https_url = "https://example.com/some/path/"
        # https url is returned unchanged
        assert absolutize_url(https_url) == https_url
        # testing with default site domain
        current_site = Site.objects.get_current()

        # test site domain without https
        current_site.domain = "example.org"
        current_site.save()
        local_path = "/foo/bar/"
        assert absolutize_url(local_path) == "https://example.org/foo/bar/"
        # trailing slash in domain doesn't result in double slash
        current_site.domain = "example.org/"
        current_site.save()
        assert absolutize_url(local_path) == "https://example.org/foo/bar/"
        # site at subdomain should work too
        current_site.domain = "example.org/sub/"
        current_site.save()
        assert absolutize_url(local_path) == "https://example.org/sub/foo/bar/"
        # site with https:// included
        current_site.domain = "https://example.org"
        assert absolutize_url(local_path) == "https://example.org/sub/foo/bar/"

        with override_settings(DEBUG=True):
            assert absolutize_url(local_path) == "https://example.org/sub/foo/bar/"
            mockrqst = Mock(scheme="http")
            assert (
                absolutize_url(local_path, mockrqst)
                == "http://example.org/sub/foo/bar/"
            )

    def test_custom_tag_string(self):
        assert custom_tag_string("foo") == ["foo"]
        assert custom_tag_string("multi-word tag") == ["multi-word tag"]
        assert custom_tag_string('"legal query", responsa') == [
            "legal query",
            "responsa",
        ]
        assert custom_tag_string("") == []
        assert custom_tag_string(
            '"Arabic script", "fiscal document",foods,Ḥalfon b. Menashshe'
        ) == ["Arabic script", "fiscal document", "foods", "Ḥalfon b. Menashshe"]


class TestCustomEmptyFieldListFilter:
    def test_title(self):
        """Accepts a custom title for the filter"""
        MyFilter = custom_empty_field_list_filter("my title")
        filter = MyFilter(
            field=Mock(),
            request=Mock(),
            params={},
            model=Mock(),
            model_admin=Mock(),
            field_path=Mock(),
        )
        assert filter.title == "my title"

    def test_options(self):
        """Accepts custom labels for the empty and non-empty filter options"""
        MyFilter = custom_empty_field_list_filter(
            "my title", empty_label="nope", non_empty_label="yep"
        )
        filter = MyFilter(
            field=Mock(),
            request=Mock(),
            params={},
            model=Mock(),
            model_admin=Mock(),
            field_path=Mock(),
        )
        choices = filter.choices(Mock())
        assert choices[1]["display"] == "nope"
        assert choices[2]["display"] == "yep"


class SortModelTester(models.Model):
    name = models.CharField(max_length=10)
    name_sort = NaturalSortField("name")

    class Meta:
        managed = False


class TestNaturalSortField:
    def test_init(self):
        assert SortModelTester._meta.get_field("name_sort").for_field == "name"

    def test_deconstruct(self):
        # test deconstruct method per django documentation
        field_instance = SortModelTester._meta.get_field("name_sort")
        name, path, args, kwargs = field_instance.deconstruct()
        new_instance = NaturalSortField(*args, **kwargs)
        assert field_instance.for_field == new_instance.for_field

    def test_presave(self):
        testmodel = SortModelTester()
        testmodel.name = "Test12.3"
        field_instance = SortModelTester._meta.get_field("name_sort")
        assert field_instance.pre_save(testmodel, None) == "test000012.000003"


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


class TestMiddleware(TestCase):
    def test_call(self):
        request = MagicMock()
        request.method = "GET"
        request.user = Mock()
        get_response = Mock()
        middleware = PublicLocaleMiddleware(get_response)

        # with logged-in user, should continue with middleware chain without modifying request
        with patch("geniza.common.middleware.translation") as mock_translation:
            request.user.is_authenticated = True
            assert middleware.__call__(request) == middleware.get_response(request)
            mock_translation.get_language_from_path.assert_not_called

        # set user to anonymous
        request.user.is_authenticated = False

        with patch("geniza.common.middleware.getattr") as mock_get_public_languages:
            # try to access path with language that is not in PUBLIC_SITE_LANGUAGES
            mock_get_public_languages.return_value = ["en", "he"]
            request.path_info = "/ar/test"
            # should call set_language
            with patch("geniza.common.middleware.set_language") as mock_set_language:
                middleware.__call__(request)
                mock_set_language.assert_called_once
            # should redirect to default language version of page
            response = middleware.__call__(request)
            assert isinstance(response, HttpResponseRedirect)
            assert response.url == "/%s/test" % settings.LANGUAGE_CODE

            # try to access path with language that _is_ in PUBLIC_SITE_LANGUAGES
            request.path_info = "/en/test"
            with patch("geniza.common.middleware.set_language") as mock_set_language:
                response = middleware.__call__(request)
                # should not call set_language
                mock_set_language.assert_not_called
                # should not redirect
                assert not isinstance(response, HttpResponseRedirect)
                # should continue with middleware chain instead
                assert response == middleware.get_response(request)


# range widget and field tests copied from mep (previously derrida via ppa)


def test_range_widget():
    # range widget decompress logic
    assert RangeWidget().decompress((None, None)) == [None, None]
    assert RangeWidget().decompress(None) == [None, None]
    assert RangeWidget().decompress((100, None)) == [100, None]
    assert RangeWidget().decompress((None, 250)) == [None, 250]
    assert RangeWidget().decompress((100, 250)) == [100, 250]
    assert RangeWidget().decompress(("100", "250")) == [100, 250]


def test_range_field():
    # range widget decompress logic
    assert RangeField().compress([]) is None
    assert RangeField().compress([100, None]) == (100, None)
    assert RangeField().compress([None, 250]) == (None, 250)
    assert RangeField().compress([100, 250]) == (100, 250)

    # out of order should raise exception
    with pytest.raises(ValidationError):
        RangeField().compress([200, 100])

    # test_set_min_max
    rangefield = RangeField()
    rangefield.set_min_max(1910, 1930)
    assert rangefield.widget.attrs["min"] == 1910
    assert rangefield.widget.attrs["max"] == 1930
    start_widget, end_widget = rangefield.widget.widgets
    assert start_widget.attrs["placeholder"] == 1910
    assert end_widget.attrs["placeholder"] == 1930
