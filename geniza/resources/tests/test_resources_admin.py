import pytest
from django.contrib import admin

from geniza.resources.admin import ManualAdmin
from geniza.resources.models import Manual


@pytest.mark.django_db
class TestManualAdmin:
    def test_url_display(self):
        manual = Manual.objects.create(
            name="Manual", url="https://geniza.princeton.edu/"
        )
        manual_admin = ManualAdmin(model=Manual, admin_site=admin.site)
        # should open in new tab
        assert 'target="_blank"' in manual_admin.url_display(manual)
        # should include security risk prevention
        assert 'rel="noopener noreferrer"' in manual_admin.url_display(manual)
        # should include accessibility label
        assert "(opens in a new tab)" in manual_admin.url_display(manual)
