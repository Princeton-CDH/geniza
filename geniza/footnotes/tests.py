from django.test import TestCase

from geniza.footnotes.models import SourceType

class TestSourceType:
    def test_str(self):
        st = SourceType(type='Edition')
        assert str(st) == st.type