from geniza.corpus.models import Collection, LanguageScript


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
