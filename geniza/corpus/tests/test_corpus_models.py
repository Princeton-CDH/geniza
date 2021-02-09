from geniza.corpus.models import Library, LanguageScript


class TestLibrary:

    def test_str(self):
        lib = Library(name='British Library', abbrev='BL')
        assert str(lib) == lib.name


class TestLanguageScripts:
    def test_str(self):
        # test display_name overwrite
        lang = LanguageScript(display_name='Judaeo-Arabic', language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == lang.display_name

        # test proper string formatting
        lang = LanguageScript(language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == 'Judaeo-Arabic (Hebrew script)'
        lang = LanguageScript(language='Judaeo-Arabic')
        assert str(lang) == lang.language