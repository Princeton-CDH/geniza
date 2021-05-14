import pytest
from unittest.mock import Mock
from django.contrib.auth.models import Group, User
from django.test import TestCase

from geniza.common.admin import LocalUserAdmin, custom_empty_field_list_filter


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
