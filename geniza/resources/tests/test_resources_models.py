import pytest

from geniza.resources.models import Manual


@pytest.mark.django_db
class TestManual:
    def test_str(self):
        # should use name as string representation
        manual = Manual.objects.create(
            name="Manual", url="https://geniza.princeton.edu/"
        )
        assert str(manual) == "Manual"
