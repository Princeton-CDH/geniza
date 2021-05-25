from unittest.mock import patch

import pytest

from geniza.footnotes.models import Creator, Footnote, SourceLanguage, SourceType


class TestSourceType:
    def test_str(self):
        st = SourceType(type="Edition")
        assert str(st) == st.type


class TestSourceLanguage:
    def test_str(self):
        eng = SourceLanguage(name="English", code="en")
        assert str(eng) == eng.name


class TestSource:
    @pytest.mark.django_db
    def test_str(self, source, twoauthor_source, multiauthor_untitledsource):
        # source has no year; str should be creator lastname, title,
        assert str(source) == "%s, %s" % (
            source.authors.first().last_name,
            source.title,
        )
        # set a year
        source.year = 1984
        assert str(source) == "%s, %s (1984)" % (
            source.authors.first().last_name,
            source.title,
        )

        # two authors
        assert str(twoauthor_source) == "%s and %s, %s" % (
            twoauthor_source.authors.first().last_name,
            twoauthor_source.authors.all()[1].last_name,
            twoauthor_source.title,
        )

        # four authors, no title
        lastnames = [
            a.creator.last_name for a in multiauthor_untitledsource.authorship_set.all()
        ]
        assert str(multiauthor_untitledsource) == "%s, %s, %s and %s" % tuple(lastnames)

    @pytest.mark.django_db
    def test_str_article(self, article):

        # article with title, journal title, volume, year
        assert str(article) == '%s, "%s" %s %s (%s)' % (
            article.authors.first().last_name,
            article.title,
            article.journal,
            article.volume,
            article.year,
        )
        # article with no title
        article.title = ""
        assert str(article) == "%s, %s %s (%s)" % (
            article.authors.first().last_name,
            article.journal,
            article.volume,
            article.year,
        )
        # no volume
        article.volume = ""
        assert str(article) == "%s, %s (%s)" % (
            article.authors.first().last_name,
            article.journal,
            article.year,
        )

    def test_all_authors(self, twoauthor_source):
        author1, author2 = twoauthor_source.authorship_set.all()
        assert twoauthor_source.all_authors() == "%s; %s" % (
            author1.creator,
            author2.creator,
        )


class TestFootnote:
    @pytest.mark.django_db
    def test_str(self, source):
        footnote = Footnote(source=source)
        # patch in a mock content object for testing
        with patch.object(Footnote, "content_object", new="foo"):
            assert str(footnote) == "Footnote of foo"
            # test some document relationship types
            footnote.doc_relation = [Footnote.EDITION]
            assert str(footnote) == "Edition of foo"
            footnote.doc_relation = [Footnote.EDITION, Footnote.TRANSLATION]
            assert str(footnote) == "Edition and Translation of foo"

    @pytest.mark.django_db
    def test_has_transcription(self, source):
        footnote = Footnote(source=source)
        # if there's content, that indicates a digitized transcription
        with patch.object(Footnote, "content_object", new="foo"):
            assert not footnote.has_transcription()
            footnote.content = "The digitized transcription"
            assert footnote.has_transcription()

    def test_display(self, source):
        footnote = Footnote(source=source)
        assert footnote.display() == "Orwell, A Nice Cup of Tea."

        footnote.location = "p. 55"
        assert footnote.display() == "Orwell, A Nice Cup of Tea, p. 55."

        footnote.notes = "With minor edits."
        assert (
            footnote.display() == "Orwell, A Nice Cup of Tea, p. 55. With minor edits."
        )

    @pytest.mark.django_db
    def test_has_url(self, source):
        footnote = Footnote(source=source)
        assert not footnote.has_url()
        footnote.url = "http://example.com/"
        assert footnote.has_url()


class TestCreator:
    def test_str(self):
        creator = Creator(last_name="Angelou", first_name="Maya")
        str(creator) == "Angelou, Maya"

        # no firstname
        assert str(Creator(last_name="Goitein")) == "Goitein"

    def test_natural_key(self):
        creator = Creator(last_name="Angelou", first_name="Maya")
        assert creator.natural_key() == ("Angelou", "Maya")

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        creator = Creator.objects.create(last_name="Angelou", first_name="Maya")
        assert Creator.objects.get_by_natural_key("Angelou", "Maya") == creator


class TestAuthorship:
    @pytest.mark.django_db
    def test_str(self, source):
        author = source.authors.first()
        authorship = source.authorship_set.first()
        str(authorship) == '%s, first author on "%s"' % (author, source.title)
