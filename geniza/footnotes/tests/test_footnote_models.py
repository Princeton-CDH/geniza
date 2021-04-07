from unittest.mock import patch

import pytest

from geniza.footnotes.models import Authorship, Creator, Footnote, Source, \
    SourceLanguage, SourceType


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
    def test_str(self, source):
        # source has no year; str should be title, creators
        assert str(source) == \
            '%s, %s' % (source.title, source.authors.first())
        # set a year
        source.year = 1984
        assert str(source) == \
            '%s (1984), %s' % (source.title, source.authors.first())

    def test_all_authors(self, twoauthor_source):
        author1, author2 = twoauthor_source.authorship_set.all()
        assert twoauthor_source.all_authors() == \
            '%s; %s' % (author1.creator, author2.creator)


class TestFootnote:

    @pytest.mark.django_db
    def test_str(self, source):
        footnote = Footnote(source=source)
        # patch in a mock content object for testing
        with patch.object(Footnote, 'content_object', new='foo'):
            assert str(footnote) == 'Footnote on foo (%s)' % source


class TestCreator:

    def test_str(self):
        creator = Creator(last_name='Angelou', first_name='Maya')
        str(creator) == 'Angelou, Maya'


class TestAuthorship:

    @pytest.mark.django_db
    def test_str(self):
        creator = Creator.objects.create(last_name='Angelou', first_name='Maya')
        essay = SourceType.objects.create(type='Essay')
        cup_of_tea = Source.objects.create(
            title='A Nice Cup of Tea',
            source_type=essay)
        creation = Authorship.objects.create(
            creator=creator, source=cup_of_tea)
        assert str(creation) == '%s 1 on "A Nice Cup of Tea"' % creator
