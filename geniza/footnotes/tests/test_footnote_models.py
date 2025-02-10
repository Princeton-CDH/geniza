from unittest.mock import patch

import pytest
from django.contrib.humanize.templatetags.humanize import ordinal
from django.utils.html import strip_tags

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
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
        # English should not show up in citation
        article.languages.add(SourceLanguage.objects.get(code="en"))
        assert "English" not in str(article)
        # unspecified language should not show up in citation
        article.languages.add(SourceLanguage.objects.get(code="zxx"))
        assert "Unspecified" not in str(article)
        # other non-english languages should
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

    def test_all_languages(self, article, twoauthor_source):
        # should comma-separate multiple languages
        article.languages.add(SourceLanguage.objects.get(name="English"))
        article.languages.add(SourceLanguage.objects.get(name="Hebrew"))
        assert article.all_languages() == "(in English, Hebrew)"
        # should be an empty string if no languages attached
        assert twoauthor_source.all_languages() == ""

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
        # should use source type for title
        lastnames = [
            a.creator.last_name for a in multiauthor_untitledsource.authorship_set.all()
        ]
        assert (
            multiauthor_untitledsource.formatted_display()
            == "%s, %s, %s and %s, %s."
            % tuple([*lastnames, multiauthor_untitledsource.source_type.type.lower()])
        )

    @pytest.mark.django_db
    def test_formatted_mlmodel(self):
        (model, _) = SourceType.objects.get_or_create(type="Machine learning model")
        (source, _) = Source.objects.get_or_create(
            title_en="HTR for PGP model 1.0",
            source_type=model,
        )
        assert (
            source.formatted_display()
            == "Machine-generated transcription (%s)." % source.title_en
        )

    def test_formatted_indexcard(self, index_cards):
        assert "unpublished index cards (1950–85)" in index_cards.formatted_display(
            format_index_cards=True
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
            assert source.uri == f"http://example.com/sources/{source.pk}/"

    def test_from_uri(self, source):
        # should get a source from its generated URI
        assert Source.from_uri(source.uri).pk == source.pk

        # should raise error on improperly formatted URI
        with pytest.raises(ValueError):
            Source.from_uri("http://example.com/")
        with pytest.raises(ValueError):
            Source.from_uri("http://example.com/1")
        with pytest.raises(Source.DoesNotExist):
            Source.from_uri("http://example.com/-1/")


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

    def test_display(self, source, multiauthor_untitledsource, goitein_editions):
        footnote = Footnote(source=source)
        assert footnote.display() == "George Orwell, A Nice Cup of Tea (n.p., n.d.)."

        footnote.location = "p. 55"  # should not change display
        footnote.notes = "With minor edits."  # should not change display
        assert footnote.display() == "George Orwell, A Nice Cup of Tea (n.p., n.d.)."

        # test handling unpublished records
        footnote.source = multiauthor_untitledsource
        assert footnote.display() == "Khan, Rustow, Vanthieghem and el-Leithy."
        footnote.doc_relation = Footnote.EDITION
        assert (
            footnote.display() == "Khan, Rustow, Vanthieghem and el-Leithy's edition."
        )
        multiauthor_untitledsource.year = "2025"
        assert (
            footnote.display()
            == "Khan, Rustow, Vanthieghem and el-Leithy's edition (2025)."
        )
        footnote.emendations = "Alan Elbaum, 2025"
        assert (
            footnote.display()
            == "Khan, Rustow, Vanthieghem and el-Leithy's edition (2025), with minor emendations by Alan Elbaum, 2025."
        )

        # test goitein unpublished
        footnote = Footnote(source=goitein_editions)
        footnote.doc_relation = Footnote.DIGITAL_EDITION
        assert footnote.display() == "S. D. Goitein's unpublished edition (1950–85)."

    def test_display_multiple(
        self,
        index_cards,
        goitein_editions,
        multiauthor_untitledsource,
        document,
    ):
        assert not Footnote.display_multiple([])
        idx_footnote_1 = Footnote(
            source=index_cards,
            location="Card #1234",
            doc_relation=Footnote.DISCUSSION,
            content_object=document,
        )
        idx_footnote_2 = Footnote(
            source=index_cards,
            location="Card #5678",
            url="http://localhost:8000",
            doc_relation=Footnote.DISCUSSION,
            content_object=document,
        )
        assert (
            Footnote.display_multiple([idx_footnote_1, idx_footnote_2])
            == 'S. D. Goitein, unpublished index cards (1950–85), #1234 and <a href="http://localhost:8000">#5678</a>. Princeton Geniza Lab, Princeton University.'
        )
        goitein_ed_fn_1 = Footnote(
            source=goitein_editions,
            doc_relation=Footnote.EDITION,
            content_object=document,
        )
        goitein_ed_fn_2 = Footnote(
            source=goitein_editions,
            doc_relation=Footnote.DIGITAL_EDITION,
            emendations="Alan Elbaum, 2025",
            content_object=document,
        )
        assert Footnote.display_multiple([goitein_ed_fn_1, goitein_ed_fn_2]).startswith(
            "S. D. Goitein's unpublished edition (1950–85), with minor emendations by Alan Elbaum, 2025, available online through the Princeton Geniza Project at <a href="
        )
        unpub_fn_1 = Footnote(
            source=multiauthor_untitledsource,
            doc_relation=Footnote.DIGITAL_EDITION,
            content_object=document,
        )
        unpub_fn_2 = Footnote(
            source=multiauthor_untitledsource,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
            emendations="Alan Elbaum, 2025",
            content_object=document,
        )
        assert Footnote.display_multiple([unpub_fn_1, unpub_fn_2]).startswith(
            "Khan, Rustow, Vanthieghem and el-Leithy's digital edition and digital translation, with minor emendations by Alan Elbaum, 2025, available online through the Princeton Geniza Project at <a href="
        )

    @pytest.mark.django_db
    def test_has_url(self, source):
        footnote = Footnote(source=source)
        assert not footnote.has_url()
        footnote.url = "http://example.com/"
        assert footnote.has_url()

    def test_content_html(self, annotation, twoauthor_source):
        # should get each associated annotation's body text, separated by newline
        canvas_uri = annotation.content["target"]["source"]["id"]
        digital_edition = annotation.footnote
        # create a second annotation
        second_annotation = Annotation.objects.create(
            footnote=digital_edition,
            content={
                **annotation.content,
                "body": [{"label": "A label", "value": "Second annotation!"}],
            },
        )
        assert isinstance(digital_edition.content_html, dict)
        assert canvas_uri in digital_edition.content_html
        # annotations are on the same canvas
        assert digital_edition.content_html[canvas_uri] == [
            "Test annotation",
            "<h3>A label</h3>",
            "Second annotation!",
        ]

        # should respect reordering
        second_annotation.content["schema:position"] = 1
        second_annotation.save()
        annotation.content["schema:position"] = 2
        annotation.save()
        # invalidate cache
        del digital_edition.content_html
        assert digital_edition.content_html[canvas_uri] == [
            "<h3>A label</h3>",
            "Second annotation!",
            "Test annotation",
        ]

        # should return None if there are no associated annotations
        edition = Footnote.objects.create(
            source=digital_edition.source,
            content_object=digital_edition.content_object,
            doc_relation=[Footnote.EDITION],
        )
        assert edition.content_html == {}

        # should return empty dict if there are no annotations
        digital_edition.annotation_set.all().delete()
        # delete the cached value from cached property
        del digital_edition.content_html
        assert digital_edition.content_html == {}

    def test_content_text(self, annotation):
        assert annotation.footnote.content_text == strip_tags(annotation.body_content)

    def test_content_text_entities(self, annotation):
        annotation.content["body"][0]["value"] = "annotation with entities &amp; &gt;"
        annotation.save()
        source = annotation.footnote.source
        document = annotation.footnote.content_object
        digital_edition_fnote = document.digital_editions()[0]
        assert digital_edition_fnote.content_text == "annotation with entities & >"

    def test_content_text_empty(self, source, document):
        edition = Footnote.objects.create(
            source=source, content_object=document, doc_relation=[Footnote.EDITION]
        )
        # should be unset, but not be the string "None"
        assert edition.content_text == None
        assert edition.content_text != "None"

    def test_explicit_line_numbers(self, document, source):
        # should parse html to include line numbers in li "value" attribute
        digital_edition = Footnote.objects.create(
            source=source,
            content_object=document,
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        Annotation.objects.create(
            footnote=digital_edition,
            content={
                "body": [{"value": "<ol><li>one</li><li>two</li></ol><p>test</p>"}],
            },
        )
        assert (
            Footnote.explicit_line_numbers(digital_edition.content_html_str)
            == '<ol><li value="1">one</li><li value="2">two</li></ol><p>test</p>'
        )

        # should respect ol "start" attribute in li "value" attributes
        doc2 = Document.objects.create()
        digital_edition2 = Footnote.objects.create(
            content_object=doc2, source=source, doc_relation=[Footnote.DIGITAL_EDITION]
        )
        Annotation.objects.create(
            footnote=digital_edition2,
            content={
                "body": [{"value": '<ol start="5"><li>one</li><li>two</li></ol>'}],
            },
        )
        assert (
            Footnote.explicit_line_numbers(digital_edition2.content_html_str)
            == '<ol start="5"><li value="5">one</li><li value="6">two</li></ol>'
        )

        # should NOT add any value attributes to unordered list li
        doc3 = Document.objects.create()
        digital_edition3 = Footnote.objects.create(
            content_object=doc3, source=source, doc_relation=[Footnote.DIGITAL_EDITION]
        )
        Annotation.objects.create(
            footnote=digital_edition3,
            content={
                "body": [{"value": '<ul start="5"><li>one</li><li>two</li></ul>'}],
            },
        )
        assert "li value" not in Footnote.explicit_line_numbers(
            digital_edition3.content_html_str
        )

        # handle None as input
        assert Footnote.explicit_line_numbers(None) is None


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
