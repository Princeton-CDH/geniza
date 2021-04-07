import pytest
from django.test import TestCase

from geniza.footnotes.models import Creator, Footnote, Source, SourceLanguage,\
    SourceType


class TestSourceType:

    def test_str(self):
        st = SourceType(type='Edition')
        assert str(st) == st.type


class TestSourceLanguage:

    def test_str(self):
        eng = SourceLanguage(name='English', code='en')
        assert str(eng) == eng.name


class TestSource:

    @pytest.mark.django_db
    def test_str(self):
        orwell = Creator.objects.create(last_name='Orwell', first_name='George')
        essay = SourceType.objects.create(type='Essay')
        english = SourceLanguage.objects.get(name='English')
        cup_of_tea = Source.objects.create(
            title='A Nice Cup of Tea',
            source_type=essay)
        cup_of_tea.languages.add(english)
        cup_of_tea.creators.add(orwell)

        assert str(cup_of_tea) == f'{orwell}. "{cup_of_tea.title}"'

    def test_all_creators(self):
        pass


class TestFootnote:

    @pytest.mark.django_db
    def test_str(self):
        orwell = Creator.objects.create(last_name='Orwell', first_name='George')
        essay = SourceType.objects.create(type='Essay')
        english = SourceLanguage.objects.get(name='English')
        cup_of_tea = Source.objects.create(
            title='A Nice Cup of Tea',
            source_type=essay)
        cup_of_tea.languages.add(english)
        cup_of_tea.creators.add(orwell)

        footnote = Footnote(source=cup_of_tea)
        assert str(footnote) == str(cup_of_tea)


class TestCreator:

    def test_str(self):
        creator = Creator(last_name='Angelou', first_name='Maya')
        str(creator) == 'Angelou, Maya'
