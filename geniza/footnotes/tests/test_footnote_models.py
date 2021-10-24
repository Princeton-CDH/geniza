from unittest.mock import patch

import pytest

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
    def test_str(
        self,
        source_article,
        source_book,
        source,
        twoauthor_source,
        multiauthor_untitledsource,
    ):
        # Source is article
        assert str(
            source_article
        ) == '{name}, "{title}" ({language}), {journal} {volume} ({year}): {pages}'.format(
            name=source_article.authors.first().firstname_lastname(),
            title=source_article.title,
            language=", ".join([l.name for l in source_article.languages.all()]),
            journal=source_article.journal,
            volume=source_article.volume,
            year=source_article.year,
            pages=source_article.page_range,
        )
        # Source is book
        assert str(
            source_book
        ) == "{name}, {title}, in {language} ({year}), {volume}, {pages}".format(
            name=source_book.authors.first().firstname_lastname(),
            title=source_book.title,
            language=", ".join([l.name for l in source_book.languages.all()]),
            journal=source_book.journal,
            volume=source_book.volume,
            year=source_book.year,
            pages=source_book.page_range,
        )
        # source has no year; str should be creator lastname, title,
        assert str(source) == "%s, %s" % (
            source.authors.first().firstname_lastname(),
            source.title,
        )
        # set a year
        source.year = 1984
        assert str(source) == "%s, %s (1984)" % (
            source.authors.first().firstname_lastname(),
            source.title,
        )

        # two authors
        assert str(twoauthor_source) == "%s and %s, %s," % (
            twoauthor_source.authors.first().firstname_lastname(),
            twoauthor_source.authors.all()[1].firstname_lastname(),
            twoauthor_source.title,
        )

        # four authors, no title
        lastnames = [
            a.creator.last_name for a in multiauthor_untitledsource.authorship_set.all()
        ]
        assert str(multiauthor_untitledsource) == "%s, %s, %s and %s" % tuple(lastnames)

        #                                            #
        #  Test formatting for specific Source types #
        #                                            #

        # Source is Blog
        # TODO formatting for Blog is not outlined in Issue 252

        # Source is Book
        # Moshe Gil, Palestine during the First Muslim Period, 634–1099, in Hebrew (Tel Aviv, 1983), vol. 2, doc. 134
        test_case = Source.objects.filter(
            title="Palestine During the First Muslim Period (634–1099)",
            source_type__type="Book",
        ).first()
        if test_case:
            assert (
                str(test_case)
                == """Moshe Gil, Palestine during the First Muslim Period, 634–1099, in Hebrew (Tel Aviv, 1983), vol. 2, doc. 134"""
            )

        # Source is Book Section
        # Outhwaite, "Byzantium and Byzantines in the Cairo Genizah: New and Old Sources," in <i>Jewish Reception of Greek Bible Versions</i> ([Missing], 2009), x:xx-xx
        test_case = Source.objects.filter(
            title="Byzantium and Byzantines in the Cairo Genizah: New and Old Sources",
            source_type__type="Book Section",
        ).first()
        if test_case:
            assert (
                str(test_case)
                == """Outhwaite, "Byzantium and Byzantines in the Cairo Genizah: New and Old Sources," in <i>Jewish Reception of Greek Bible Versions</i> (2009)"""
            )

        if s.source_type.type == "Book Section":
            assert (
                str(s)
                == f'{author}, "{s.title}," {"in <i>"+s.journal+"</i>" if s.journal else ""} {"("+str(s.year)+")," if s.year else ""}{" "+s.volume+": " if s.volume else ""}{str(s.page_range) if s.page_range else ""}'
            )

        # Source is Dissertation
        # Ṣabīḥ ʿAodeh, "Eleventh Century Arabic Letters of Jewish Merchants from the Cairo Geniza" (PhD diss. Tel Aviv University, 1992)
        test_case = Source.objects.filter(
            title="Eleventh Century Arabic Letters of Jewish Merchants from the Cairo Geniza",
            source_type__type="Dissertation",
        ).first()
        if test_case:
            assert (
                str(test_case)
                == """Ṣabīḥ ʿAodeh, "Eleventh Century Arabic Letters of Jewish Merchants from the Cairo Geniza" (PhD diss. Tel Aviv University, 1992)"""
            )

        if s.source_type.type == "Dissertation":
            assert (
                str(s)
                == f'{author}, "{s.title}" {"in "+languages+")" if languages else ""}, {"("+s.other_info+", "+str(s.year)+")" if s.other_info and s.year else ""}'
            )

        # Source is Unpublished
        # TODO formatting for Blog is not outlined in Issue 252

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
        assert footnote.display() == "George Orwell, A Nice Cup of Tea."

        footnote.location = "p. 55"
        assert footnote.display() == "George Orwell, A Nice Cup of Tea, p. 55."

        footnote.notes = "With minor edits."
        assert (
            footnote.display()
            == "George Orwell, A Nice Cup of Tea, p. 55. With minor edits."
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
            content="{'foo': 'bar'}",
        )
        assert not Footnote.objects.filter(pk=footnote1.pk).includes_footnote(footnote2)
        assert (
            Footnote.objects.filter(pk=footnote1.pk).includes_footnote(
                footnote2, include_content=False
            )
            == footnote1
        )


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

    def test_firstname_lastname(self):
        creator = Creator(last_name="Angelou", first_name="Maya")
        assert creator.firstname_lastname() == "Maya Angelou"

        # no firstname
        assert Creator(last_name="Goitein").firstname_lastname() == "Goitein"


class TestAuthorship:
    @pytest.mark.django_db
    def test_str(self, source):
        author = source.authors.first()
        authorship = source.authorship_set.first()
        str(authorship) == '%s, first author on "%s"' % (author, source.title)
