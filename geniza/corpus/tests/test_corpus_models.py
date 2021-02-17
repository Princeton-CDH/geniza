import pytest

from geniza.corpus.models import Collection, CollectionManager, LanguageScript


class TestCollection:

    def test_str(self):
        lib = Collection(library='British Library', abbrev='BL')
        assert str(lib) == lib.abbrev

    def test_natural_key(self):
        lib = Collection(library='British Library', abbrev='BL')
        assert lib.natural_key() == ('BL',)


@pytest.mark.django_db
class TestCollectionManager:

    def test_get_by_natural_key(self):
        lib = Collection.objects.create(library='British Library', abbrev='BL')

        assert Collection.objects.get_by_natural_key('BL') == lib


class TestLanguageScripts:
    def test_str(self):
        # test display_name overwrite
        lang = LanguageScript(display_name='Judaeo-Arabic', language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == lang.display_name

        # test proper string formatting
        lang = LanguageScript(language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == 'Judaeo-Arabic (Hebrew script)'
