from geniza.corpus.models import Collection, Fragment, LanguageScript


class TestCollection:

    def test_str(self):
        lib = Collection(library='British Library', abbrev='BL')
        assert str(lib) == lib.abbrev


class TestLanguageScripts:
    def test_str(self):
        # test display_name overwrite
        lang = LanguageScript(display_name='Judaeo-Arabic', language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == lang.display_name

        # test proper string formatting
        lang = LanguageScript(language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == 'Judaeo-Arabic (Hebrew script)'


class TestFragment:

    def test_str(self):
        frag = Fragment(shelfmark='TS 1')
        assert str(frag) == frag.shelfmark

    def test_is_multifragment(self):
        frag = Fragment(shelfmark='TS 1')
        assert not frag.is_multifragment()

        frag.multifragment = 'a'
        assert frag.is_multifragment()
