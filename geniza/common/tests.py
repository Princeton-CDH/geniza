import random
import time
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from pytest_django.asserts import assertContains
from taggit.models import Tag

from geniza.common.admin import (
    CustomTagAdmin,
    LocalLogEntryAdmin,
    LocalUserAdmin,
    TagForm,
    custom_empty_field_list_filter,
)
from geniza.common.fields import NaturalSortField, RangeField, RangeWidget
from geniza.common.metadata_export import Exporter, LogEntryExporter
from geniza.common.middleware import PublicLocaleMiddleware
from geniza.common.models import UserProfile
from geniza.common.utils import (
    Echo,
    Timer,
    Timerable,
    absolutize_url,
    custom_tag_string,
)
from geniza.common.views import TagAutocompleteView
from geniza.corpus.models import Document


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
    @override_settings(ENV="test")  # behaves differently for development environment
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

    @pytest.mark.django_db
    @override_settings(ENV="development")
    def test_absolutize_url_dev(self):
        local_path = "/foo/bar/"
        # should not be https
        assert absolutize_url(local_path) == "http://example.com/foo/bar/"

    def test_custom_tag_string(self):
        assert custom_tag_string("foo") == ["foo"]
        # should correctly parse multi-word tags
        assert custom_tag_string("multi-word tag") == ["multi-word tag"]
        # should parse when mixed with single word tags
        assert custom_tag_string('"legal query", responsa') == [
            "legal query",
            "responsa",
        ]
        assert custom_tag_string("") == []
        # should remove diacritics
        diacritics_tags = custom_tag_string(
            '"Arabic script", "fiscal document",foods,Ḥalfon b. Menashshe'
        )
        assert all(
            [
                item in diacritics_tags
                for item in [
                    "Arabic script",
                    "fiscal document",
                    "foods",
                    "Halfon b. Menashshe",
                ]
            ]
        )


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
        change_list = Mock()
        change_list.add_facets = False
        choices = filter.choices(change_list)
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


@pytest.mark.django_db
def test_userprofile_str(admin_user):
    profile = UserProfile.objects.create(user=admin_user)
    assert str(profile) == "User profile for %s" % admin_user


# migration test case adapted from
# https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# and copied from mep-django


class TestMigrations(TransactionTestCase):
    # Base class for migration test case

    # NOTE: subclasses must be marked with @pytest.mark.order("last")
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


@pytest.mark.django_db
class TestCustomTagAdmin:
    def test_get_queryset(self):
        document1 = Document.objects.create()
        document2 = Document.objects.create()
        tag_name = "Tag_Ex"
        document1.tags.add(tag_name)
        document2.tags.add(tag_name)

        tag_admin = CustomTagAdmin(model=Tag, admin_site=admin.site)

        request_factory = RequestFactory()
        # simulate request for tag page
        request = request_factory.post("/admin/taggit/tag/")
        qs = tag_admin.get_queryset(request)
        first_item = qs.first()
        assert hasattr(first_item, "item_count")
        assert first_item.item_count == 2

    def test_item_count(self):
        document1 = Document.objects.create()
        document2 = Document.objects.create()
        tag_name = "Tag_Ex"
        document1.tags.add(tag_name)
        document2.tags.add(tag_name)

        request_factory = RequestFactory()
        # simulate request for tag page
        request = request_factory.post("/admin/taggit/tag/")
        tag_admin = CustomTagAdmin(model=Tag, admin_site=admin.site)

        qs = tag_admin.get_queryset(request)
        item_count = tag_admin.item_count(qs.first())

        assert item_count == 2

    def test_merge_tags(self):
        # adapted from test_corpus_admin.TestDocumentAdmin.test_merge_document
        mockrequest = Mock()
        test_ids = ["123", "456", "7698"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = CustomTagAdmin(Tag, Mock()).merge_tags(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 303
        assert resp["location"].startswith(reverse("admin:tag-merge"))
        assert resp["location"].endswith("?ids=%s" % ",".join(test_ids))

        test_ids = ["123"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = CustomTagAdmin(Tag, Mock()).merge_tags(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 302
        assert resp["location"] == reverse("admin:taggit_tag_changelist")


@pytest.mark.django_db
class TestTagForm:
    def test_form_clean(self):
        Tag.objects.create(name="test name", slug="test-name")
        # should raise a validation error on the "name" field if a tag with
        # the same name exists, case-insensitive
        form = TagForm()
        form.cleaned_data = {"name": "Test Name", "slug": "test-name-2"}
        form.clean()
        assert "name" in form.errors


def test_echo():
    echo = Echo()

    value = random.random()
    assert value is echo.write(value)

    with Echo() as e:
        assert type(e) == Echo


# db access necessary because Exporter.__init__ will access Site information
@pytest.mark.django_db
def test_base_exporter():
    exporter = Exporter()

    # raises correct error?
    with pytest.raises(NotImplementedError):
        exporter.get_export_data_dict(obj=None)

    # serializes correctly?
    sep = exporter.sep_within_cells
    # should preserve order passed in
    assert exporter.serialize_value([1, 2, 3]) == f"1{sep}2{sep}3"
    assert exporter.serialize_value([1, 3, 2]) == f"1{sep}3{sep}2"
    assert (
        exporter.serialize_value({3, 2, 1}) == f"1{sep}2{sep}3"
    )  # set order not preserved
    assert exporter.serialize_dict({"key": [1, 3, 2]}) == {"key": f"1{sep}3{sep}2"}

    # keys already enforced to be strings by database
    assert exporter.serialize_dict({"0": [1, 3, 2]}) == {"0": f"1{sep}3{sep}2"}

    assert exporter.serialize_value(123) == "123"

    assert exporter.serialize_value(True) == "Y"
    assert exporter.serialize_value(False) == "N"
    assert exporter.serialize_value(None) == ""


fake_printed = ""


def fake_printer(x, end="\n"):
    global fake_printed
    fake_printed = fake_printed + x + end


def test_timer():
    with Timer(to_print=False) as t:
        pass
    assert round(t.elapsed) == 0

    with Timer(to_print=False) as t:
        time.sleep(1)
    assert round(t.elapsed) == 1

    with Timer(to_print=False) as t:
        time.sleep(2)
    assert round(t.elapsed) == 2

    timer_desc = "My Timer Description"
    with Timer(print_func=fake_printer, desc=timer_desc, to_print=False) as t:
        pass
    assert timer_desc not in fake_printed

    with Timer(print_func=fake_printer, desc=timer_desc, to_print=True) as t:
        pass
    assert timer_desc in fake_printed
    assert "completed in 0.0s" in fake_printed

    class newthing(Timerable):
        pass

    x = newthing()
    timer_desc2 = "Totally Different Timer Description"
    with x.timer(desc=timer_desc2, print_func=fake_printer, to_print=True) as t:
        pass
    assert round(t.elapsed) == 0
    assert timer_desc2 in fake_printed

    timer_desc3 = "A Thrice Different Description!"
    y = newthing()
    y.print = fake_printer
    with y.timer(desc=timer_desc3) as t:
        pass
    assert timer_desc3 in fake_printed


@pytest.mark.django_db
def test_logentry_exporter_data(document):
    logentry_exporter = LogEntryExporter()
    # document fixture has two log entries; first should be creation/addition
    logentry = document.log_entries.first()
    data = logentry_exporter.get_export_data_dict(logentry)
    assert data["action_time"] == logentry.action_time
    assert data["user"] == logentry.user
    assert data["content_type"] == logentry.content_type.name
    assert data["content_type_app"] == logentry.content_type.app_label
    assert data["object_id"] == str(document.pk)
    assert data["change_message"] == logentry.change_message
    assert data["action"] == "addition"


@pytest.mark.django_db
def test_admin_export_to_csv(document):
    logentry_admin = LocalLogEntryAdmin(model=LogEntry, admin_site=admin.site)
    response = logentry_admin.export_to_csv(Mock())
    assert isinstance(response, StreamingHttpResponse)
    # consume the binary streaming content and decode to inspect as str
    content = b"".join([val for val in response.streaming_content]).decode()

    # spot-check that we get expected data
    # - header row
    assert "action_time,user,content_type" in content
    # - some content
    for log_entry in document.log_entries.all():
        assert str(log_entry.action_time) in content
        assert log_entry.user.username in content
        # action flag converted to text
        assert LogEntryExporter.action_label[log_entry.action_flag] in content


@pytest.mark.django_db
class TestTagAutocompleteView:
    def test_get_queryset(self, rf):
        # set up some tags
        document = Document.objects.create()
        document.tags.add("Tag_Ex")
        document.tags.add("Tag2")
        document.tags.add("other")
        assert Tag.objects.count() == 3

        view = TagAutocompleteView()
        view.q = "Tag"  # search query

        # should be empty queryset with unauthenticated user
        view.request = rf.get(reverse("tag-autocomplete"))
        view.request.user = Mock()
        view.request.user.is_authenticated = False
        assert not view.get_queryset().exists()

        # should not be empty queryset with authenticated user
        view.request.user.is_authenticated = True
        qs = view.get_queryset()
        assert qs.exists()
        # should include the two tags that start with Tag
        assert qs.count() == 2

    def test_get_create_option(self):
        # should always return empty list
        view = TagAutocompleteView()
        assert view.get_create_option(Mock(), "Tag") == []


@pytest.mark.django_db
def test_language_switcher(client):
    # fake url with /en/
    current_path = "/en/documents/100/"
    response = client.get(
        reverse("common:language-switcher"), {"current_path": current_path}
    )

    # should translate the url passed via current_path query param
    assert response.status_code == 200
    assertContains(response, 'href="/ar/documents/100/"')
