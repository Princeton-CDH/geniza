import pytest
from django.db.utils import IntegrityError

from geniza.corpus.models import Collection, LanguageScript


class TestCollection:

    def test_str(self):
        lib = Collection(library='British Library', abbrev='BL')
        assert str(lib) == lib.abbrev

    def test_natural_key(self):
        lib = Collection(library='British Library', abbrev='BL')
        assert lib.natural_key() == ('BL',)

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        lib = Collection.objects.create(library='British Library', abbrev='BL')
        assert Collection.objects.get_by_natural_key('BL') == lib

    @pytest.mark.django_db
    def test_caseinsensitive_unique(self):
        Collection.objects.create(library='British Library', abbrev='BL')
        with pytest.raises(IntegrityError):
            Collection.objects.create(library='Bermuda Library', abbrev='bl')


class TestLanguageScripts:

    def test_str(self):
        # test display_name overwrite
        lang = LanguageScript(display_name='Judaeo-Arabic',
                              language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == lang.display_name

        # test proper string formatting
        lang = LanguageScript(language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == 'Judaeo-Arabic (Hebrew script)'

    def test_natural_key(self):
        lang = LanguageScript(language='Judaeo-Arabic', script='Hebrew')
        assert lang.natural_key() == (lang.language, lang.script)

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        lang = LanguageScript.objects.create(language='Judaeo-Arabic',
                                             script='Hebrew')
        assert LanguageScript.objects \
            .get_by_natural_key(lang.language, lang.script) == lang
