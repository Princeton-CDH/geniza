from unittest.mock import patch

import pytest

from geniza.footnotes.models import Creator, Footnote, SourceLanguage, \
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
    def test_str(self, source, twoauthor_source, multiauthor_untitledsource):
        # source has no year; str should be creator lastname, title,
        assert str(source) == \
            '%s, %s' % (source.authors.first().last_name, source.title)
        # set a year
        source.year = 1984
        assert str(source) == \
            '%s, %s (1984)' % (source.authors.first().last_name, source.title)

        # two authors
        assert str(twoauthor_source) == \
            '%s and %s, %s' % (
                twoauthor_source.authors.first().last_name,
                twoauthor_source.authors.all()[1].last_name,
                twoauthor_source.title)

        # four authors, no title
        lastnames = [a.creator.last_name for
                     a in multiauthor_untitledsource.authorship_set.all()]
        print(lastnames)
        assert str(multiauthor_untitledsource) == \
            '%s, %s, %s and %s' % tuple(lastnames)

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
    def test_str(self, source):
        author = source.authors.first()
        authorship = source.authorship_set.first()
        str(authorship) == \
            '%s, first author on "%s"' % (author, source.title)
