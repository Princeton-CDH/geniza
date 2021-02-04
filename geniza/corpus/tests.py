from geniza.corpus.models import Library


class TestLibrary:

    def test_str(self):
        lib = Library(name='British Library', abbrev='BL')
        assert str(lib) == lib.name
