from django.test import TestCase

from geniza.people.models import Person
from geniza.footnotes.models import SourceType, Source, Footnote
from geniza.corpus.models import LanguageScript

class TestSourceType:
    def test_str(self):
        st = SourceType(type='Edition')
        assert str(st) == st.type

class TestSource:
    def test_str(self):
        orwell = Person(first_name='George', last_name='Orwell')
        essay = SourceType(type='Essay')
        english = LanguageScript(language='English', script='English')
        cup_of_tea = Source(author=orwell, title='A Nice Cup of Tea', 
            source_type=essay, language=english)

        assert str(cup_of_tea) == cup_of_tea.title

class TestFootnote:
    def test_str(self):
        orwell = Person(first_name='George', last_name='Orwell')
        essay = SourceType(type='Essay')
        english = LanguageScript(language='English', script='English')
        cup_of_tea = Source(author=orwell, title='A Nice Cup of Tea', 
            source_type=essay, language=english)

        footnote = Footnote(source=cup_of_tea)
        assert str(footnote) == cup_of_tea.title