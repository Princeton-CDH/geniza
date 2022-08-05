from unittest.mock import patch

import pytest
from django.contrib.humanize.templatetags.humanize import ordinal

from geniza.footnotes.models import (
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)


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
        # source has no year; str should be creator lastname, title, (n.p., n.d.)
        assert str(source) == "%s, %s." % (
            source.authors.first().firstname_lastname(),
            source.title,
        )
        # set a year
        source.year = 1984
        assert str(source) == "%s, %s (1984)." % (
            source.authors.first().firstname_lastname(),
            source.title,
        )

        # two authors
        assert str(twoauthor_source) == "%s and %s, %s." % (
            twoauthor_source.authors.first().firstname_lastname(),
            twoauthor_source.authors.all()[1].firstname_lastname(),
            twoauthor_source.title,
        )

        # set an edition
        twoauthor_source.edition = 3
        assert str(twoauthor_source) == "%s and %s, %s, %s ed." % (
            twoauthor_source.authors.first().firstname_lastname(),
            twoauthor_source.authors.all()[1].firstname_lastname(),
            twoauthor_source.title,
            ordinal(twoauthor_source.edition),
        )

        # four authors, no title
        lastnames = [
            a.creator.last_name for a in multiauthor_untitledsource.authorship_set.all()
        ]
        assert str(multiauthor_untitledsource) == "%s, %s, %s and %s." % tuple(
            lastnames
        )

    @pytest.mark.django_db
    def test_str_article(self, article):

        # article with title, journal title, volume, year
        assert str(article) == '%s, "%s," %s %s, no. %d (%s).' % (
            article.authors.first().firstname_lastname(),
            article.title,
            article.journal,
            article.volume,
            article.issue,
            article.year,
        )
        # article with no title
        article.title_en = ""
        assert str(article) == "%s, %s %s, no. %d (%s)." % (
            article.authors.first().firstname_lastname(),
            article.journal,
            article.volume,
            article.issue,
            article.year,
        )
        # no volume or issue
        article.volume = ""
        article.issue = None
        assert str(article) == "%s, %s (%s)." % (
            article.authors.first().firstname_lastname(),
            article.journal,
            article.year,
        )

    def test_str_language(self, article):
        article.languages.add(SourceLanguage.objects.get(name="Hebrew"))
        assert "(in Hebrew)" in str(article)

    def test_str_book_section(self, book_section):
        # book section with authors, title, book title, edition, year, volume no.
        assert str(book_section) == '%s, "%s," in %s, %s ed. (%s), vol. %s.' % (
            book_section.authors.first().firstname_lastname(),
            book_section.title,
            book_section.journal,
            ordinal(book_section.edition),
            book_section.year,
            book_section.volume,
        )

    def test_all_authors(self, twoauthor_source):
        author1, author2 = twoauthor_source.authorship_set.all()
        assert twoauthor_source.all_authors() == "%s; %s" % (
            author1.creator,
            author2.creator,
        )

    def test_str_unpublished_vol(self, unpublished_editions):
        # displays with volume
        assert str(unpublished_editions) == "S. D. Goitein, unpublished editions. (CUL)"

    def test_display(self, unpublished_editions):
        # displays without volume
        assert unpublished_editions.display() == "S. D. Goitein, unpublished editions."

    def test_formatted_display(self, book_section):
        # should display proper publisher info, page range for book section fixture
        assert (
            "(%s: %s, %s), %s:%s"
            % (
                book_section.place_published,
                book_section.publisher,
                book_section.year,
                book_section.volume,
                book_section.page_range,
            )
            in book_section.formatted_display()
        )

        # should display page range without volume
        book_section.volume = ""
        assert (
            "(%s: %s, %s), %s"
            % (
                book_section.place_published,
                book_section.publisher,
                book_section.year,
                book_section.page_range,
            )
            in book_section.formatted_display()
        )

        # should dispaly n.p.: Publisher when no place published
        book_section.place_published = ""
        assert (
            "(n.p.: %s, %s)"
            % (
                book_section.publisher,
                book_section.year,
            )
            in book_section.formatted_display()
        )

    def test_formatted_phd_diss(self, phd_dissertation):
        # should include "PhD diss." and degree-granting institution;
        # should surround title in double quotes;
        # should not include publication place;
        # should end in a period
        assert (
            phd_dissertation.formatted_display()
            == '%s, "%s" (PhD diss., %s, %s).'
            % (
                phd_dissertation.authors.first().firstname_lastname(),
                phd_dissertation.title,
                phd_dissertation.publisher,
                phd_dissertation.year,
            )
        )
        assert (
            phd_dissertation.place_published
            and phd_dissertation.place_published
            not in phd_dissertation.formatted_display()
        )

    def test_formatted_no_title(self, multiauthor_untitledsource):
        # should include [digital geniza document edition]
        lastnames = [
            a.creator.last_name for a in multiauthor_untitledsource.authorship_set.all()
        ]
        assert (
            multiauthor_untitledsource.formatted_display()
            == "%s, %s, %s and %s, [digital geniza document edition]."
            % tuple(lastnames)
        )

    def test_get_volume_from_shelfmark(self):
        assert Source.get_volume_from_shelfmark("T-S 3564.5J") == "T-S 35"
        assert Source.get_volume_from_shelfmark("Bodl. 3563") == "Bodl."
        assert Source.get_volume_from_shelfmark("T-S Miscellan 36") == "T-S Misc"

    def test_formatted_source_url(self, source):
        # should create link around source title
        source.url = "http://example.com/"
        assert (
            '<a href="http://example.com/">%s</a>' % source.title
            in source.formatted_display()
        )

    @pytest.mark.django_db
    def test_uri(self, source):
        # should generate a URI using set manifest base URL with /source/pk
        with patch("geniza.footnotes.models.getattr") as mock_getattr:
            # mock getattr so we can define manifest base URL here
            mock_getattr.return_value = "http://example.com/"
            assert source.uri == f"http://example.com/source/{source.pk}"


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
            assert not footnote.has_transcription
            footnote.content = "The digitized transcription"
            assert footnote.has_transcription

    def test_display(self, source):
        footnote = Footnote(source=source)
        assert footnote.display() == "George Orwell, A Nice Cup of Tea."

        footnote.location = "p. 55"  # should not change display
        assert footnote.display() == "George Orwell, A Nice Cup of Tea."

        footnote.notes = "With minor edits."
        assert (
            footnote.display() == "George Orwell, A Nice Cup of Tea. With minor edits."
        )

    @pytest.mark.django_db
    def test_has_url(self, source):
        footnote = Footnote(source=source)
        assert not footnote.has_url()
        footnote.url = "http://example.com/"
        assert footnote.has_url()


class TestFootnoteQuerySet:
    @pytest.mark.django_db
    def test_includes_footnote(self, source, twoauthor_source, document):
        # same source, content object, location
        footnote1 = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )
        footnote2 = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )
        assert (
            Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)
            == footnote1
        )

        # different location
        footnote2.location = "p.5"
        footnote2.save()
        assert footnote1 != footnote2
        assert not Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)

        # different source
        footnote2.location = "p.1"
        footnote2.source = twoauthor_source
        footnote2.save()
        assert not Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)

        # different content object -- considered equal if all else is equal!
        footnote2.source = source
        footnote2.content_object = twoauthor_source
        footnote2.save()
        assert (
            Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)
            == footnote1
        )

        # different notes
        footnote2.notes = "some extra info"
        footnote2.save()
        assert not Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)

        # different content
        footnote2.notes = ""
        footnote2.content = "{}"
        footnote2.save()
        assert not Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)

    @pytest.mark.django_db
    def test_includes_footnote_ignore_content(self, source, twoauthor_source, document):
        # same source, content object, location; one with content
        footnote1 = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )
        footnote2 = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
            content={"text": "{'foo': 'bar'}"},
        )
        assert not Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)
        assert (
            Footnote.objects.filter(pk=footnote1.pk).includes_footnote(
                footnote2, include_content=False
            )
            == footnote1
        )

    def test_editions(self, source, twoauthor_source, document):
        # same source, content object, location
        footnote1 = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )
        footnote2 = Footnote.objects.create(
            source=source,
            content_object=document,
            location="p.1",
            doc_relation=Footnote.TRANSLATION,
        )
        editions = Footnote.objects.editions()
        assert footnote1 in editions
        assert footnote2 not in editions

        # test filter with multiple document relations
        footnote2.doc_relation = [Footnote.EDITION, Footnote.TRANSLATION]
        footnote2.save()
        assert footnote2 in Footnote.objects.editions()


class TestCreator:
    def test_str(self):
        creator = Creator(last_name_en="Angelou", first_name_en="Maya")
        str(creator) == "Angelou, Maya"

        # no firstname
        assert str(Creator(last_name_en="Goitein")) == "Goitein"

    def test_natural_key(self):
        creator = Creator(last_name_en="Angelou", first_name_en="Maya")
        assert creator.natural_key() == ("Angelou", "Maya")

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        creator = Creator.objects.create(last_name_en="Angelou", first_name_en="Maya")
        assert Creator.objects.get_by_natural_key("Angelou", "Maya") == creator

    def test_firstname_lastname(self):
        creator = Creator(last_name_en="Angelou", first_name_en="Maya")
        assert creator.firstname_lastname() == "Maya Angelou"

        # no firstname
        assert Creator(last_name_en="Goitein").firstname_lastname() == "Goitein"


class TestAuthorship:
    @pytest.mark.django_db
    def test_str(self, source):
        author = source.authors.first()
        authorship = source.authorship_set.first()
        str(authorship) == '%s, first author on "%s"' % (author, source.title)
