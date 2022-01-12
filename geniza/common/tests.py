from unittest.mock import Mock

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings

from geniza.common.admin import LocalUserAdmin, custom_empty_field_list_filter
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
