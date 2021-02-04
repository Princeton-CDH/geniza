from django.contrib.auth.models import Group, User
from django.test import TestCase
import pytest

from geniza.common.admin import LocalUserAdmin


@pytest.mark.django_db
class TestLocalUserAdmin(TestCase):

    def test_group_names(self):
        testuser = User.objects.create(username="test")
        local_useradm = LocalUserAdmin(User, '')

        assert local_useradm.group_names(testuser) is None

        grp1 = Group.objects.create(name='testers')
        grp2 = Group.objects.create(name='staff')
        grp3 = Group.objects.create(name='superusers')

        testuser.groups.add(grp1, grp2)
        group_names = local_useradm.group_names(testuser)
        assert grp1.name in group_names
        assert grp2.name in group_names
        assert grp3.name not in group_names
