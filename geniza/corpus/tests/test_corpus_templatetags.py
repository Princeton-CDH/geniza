from unittest.mock import MagicMock, Mock

import pytest
from django.http.request import HttpRequest, QueryDict
from django.urls import reverse
from piffle.image import IIIFImageClient
from pytest_django.asserts import assertContains

from geniza.common.utils import absolutize_url
from geniza.corpus.templatetags import admin_extras, corpus_extras
from geniza.footnotes.models import Footnote


class TestCorpusExtrasTemplateTags:
    def test_alphabetize(self):
        """Should lowercase and alphabetize a list of strings"""
        lst = ["Test", "hello", "abc", "Def"]
        alphabetized = corpus_extras.alphabetize(lst)
        assert alphabetized[0] == "abc"
        assert alphabetized[1] == "def"
        assert alphabetized[2] == "hello"
        assert alphabetized[3] == "test"

    def test_alphabetize_bad_list(self):
        """Should throw TypeError when list contains non-strings"""
        with pytest.raises(TypeError) as err:
            bad_list = [1, 2, 3, "hi", ["test"]]
            corpus_extras.alphabetize(bad_list)
        assert "Argument must be a list of strings" in str(err)

    def test_alphabetize_not_list(self):
        """Should throw TypeError when argument is not a list"""
        with pytest.raises(TypeError) as err:
            not_list = -4
            corpus_extras.alphabetize(not_list)
        assert "Argument must be a list of strings" in str(err)

    def test_alphabetize_empty_list(self):
        """Should process empty list without raising exception"""
        lst = []
        alphabetized = corpus_extras.alphabetize(lst)
        assert alphabetized == []

    def test_has_location_or_url(self, document, footnote):
        # footnote has a location
        assert corpus_extras.has_location_or_url([footnote]) == True
        footnote_2 = Footnote.objects.create(
            object_id=document.pk,
            content_type=footnote.content_type,
            source=footnote.source,
        )
        # footnote has no location or url
        assert corpus_extras.has_location_or_url([footnote_2]) == False
        # one of the document's footnotes has a location
        assert corpus_extras.has_location_or_url(list(document.footnotes.all())) == True

    def test_all_doc_relations(self, document, footnote):
        Footnote.objects.create(
            object_id=document.pk,
            content_type=footnote.content_type,
            source=footnote.source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        assert corpus_extras.all_doc_relations(list(document.footnotes.all())) == [
            "Digital Edition",
            "Edition",
        ]
        # should not repeat doc relations even if multiple of the same type appear
        Footnote.objects.create(
            object_id=document.pk,
            content_type=footnote.content_type,
            source=footnote.source,
            doc_relation=Footnote.EDITION,
            location="other place",
        )
        # should not include empty doc relation in list
        Footnote.objects.create(
            object_id=document.pk,
            content_type=footnote.content_type,
            source=footnote.source,
            doc_relation=[],
        )
        assert corpus_extras.all_doc_relations(list(document.footnotes.all())) == [
            "Digital Edition",
            "Edition",
        ]

    def test_handle_index_cards(self, document, footnote, index_cards, client):
        # no index card numbers
        fn = Footnote.objects.create(
            object_id=document.pk,
            content_type=footnote.content_type,
            source=index_cards,
            doc_relation=Footnote.DISCUSSION,
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "cards (1950–85). Princeton Geniza Lab")

        # one card with numbers
        fn.location = "Card #1234"
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(response, "cards (1950–85), #1234. Princeton Geniza Lab")

        # multiple cards
        Footnote.objects.create(
            object_id=document.pk,
            content_type=footnote.content_type,
            source=index_cards,
            doc_relation=Footnote.DISCUSSION,
            location="card #5678",
        )
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response, "cards (1950–85), #1234 and #5678. Princeton Geniza Lab"
        )

        # card with link
        fn.url = "https://fake.goitein.card/"
        fn.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assertContains(
            response,
            '<a href="https://fake.goitein.card/" data-turbo="false">#1234</a>',
            html=True,
        )


def test_dict_item():
    # no error on non-dict first argument
    assert corpus_extras.dict_item([], "foo") is None
    # no error on not found
    assert corpus_extras.dict_item({}, "foo") is None
    # string key
    assert corpus_extras.dict_item({"foo": "bar"}, "foo") == "bar"
    # integer key
    assert corpus_extras.dict_item({13: "lucky"}, 13) == "lucky"
    # integer value
    assert corpus_extras.dict_item({13: 7}, 13) == 7


def test_index():
    # no error on invalid index
    assert corpus_extras.index([], 12) == ""
    # valid index
    assert corpus_extras.index([1, 2, 3], 1) == 2
    # valid index, different type
    assert corpus_extras.index(["a", "b", "c"], 2) == "c"


def test_querystring_replace():
    mockrequest = Mock()
    mockrequest.GET = QueryDict("?q=contract")
    context = {"request": mockrequest}
    # replace when arg is not present
    args = corpus_extras.querystring_replace(context, page=1)
    # preserves existing args
    assert "q=contract" in args
    # adds new arg
    assert "page=1" in args

    mockrequest.GET = QueryDict("?q=contract&page=2")
    args = corpus_extras.querystring_replace(context, page=3)
    assert "q=contract" in args
    # replaces existing arg
    assert "page=3" in args
    assert "page=2" not in args

    mockrequest.GET = QueryDict("?q=contract&page=2&sort=relevance")
    args = corpus_extras.querystring_replace(context, page=10)
    assert "q=contract" in args
    assert "sort=relevance" in args
    assert "page=10" in args


def test_iiif_image():
    # copied from mep_django

    myimg = IIIFImageClient("http://image.server/path/", "myimgid")
    # check expected behavior
    assert str(corpus_extras.iiif_image(myimg, "size:width=250")) == str(
        myimg.size(width=250)
    )
    assert str(corpus_extras.iiif_image(myimg, "size:width=250,height=300")) == str(
        myimg.size(width=250, height=300)
    )
    assert str(corpus_extras.iiif_image(myimg, "format:png")) == str(
        myimg.format("png")
    )

    # check that errors don't raise exceptions
    assert corpus_extras.iiif_image(myimg, "bogus") == ""
    assert corpus_extras.iiif_image(myimg, "size:bogus") == ""
    assert corpus_extras.iiif_image(myimg, "size:bogus=1") == ""


def test_iiif_image_placeholder():
    # test for placeholder used when we have canvases that do not have iiif images
    img_url = "http://image.server/path/myimg.png"
    myimg = {"info": img_url}
    # should always just return the URL regardless of what options we pass
    assert str(corpus_extras.iiif_image(myimg, "size:width=250")) == img_url


def test_iiif_info_json():
    img1 = IIIFImageClient("http://image.server/path/", "myimgid")
    img2 = IIIFImageClient("http://image.server/path/", "myimgid2")
    imgs = [{"image": img1}, {"image": img2}]
    json_ids = corpus_extras.iiif_info_json(imgs)
    # should contain the same ids but with /info.json appended
    assert "http://image.server/path/myimgid/info.json" in json_ids
    assert "http://image.server/path/myimgid2/info.json" in json_ids


def test_pgp_urlize(document, join):
    doc_link = '<a href="{url}">PGPID {id}</a>'.format(
        url=absolutize_url(document.get_absolute_url()), id=document.id
    )
    join_link = '<a href="{url}">PGPID {id}</a>'.format(
        url=absolutize_url(join.get_absolute_url()), id=join.id
    )

    # should create links for all referenced PGPID #
    text_one_pgpid = "An example of some text with PGPID %s." % document.id
    assert doc_link in corpus_extras.pgp_urlize(text_one_pgpid)
    text_two_pgpids = "An example of sometext with PGPID %s and PGPID %s." % (
        document.id,
        join.id,
    )
    assert doc_link in corpus_extras.pgp_urlize(text_two_pgpids)
    assert (join_link + ".") in corpus_extras.pgp_urlize(text_two_pgpids)
    text_punctuation = (
        "A PGPID %s, coming before a comma, and a PGPID %s; coming before a semicolon."
        % (document.id, join.id)
    )
    assert (doc_link + ",") in corpus_extras.pgp_urlize(text_punctuation)
    assert (join_link + ";") in corpus_extras.pgp_urlize(text_punctuation)


def test_shelfmark_wrap():
    assert corpus_extras.shelfmark_wrap("foo") == "<span>foo</span>"
    assert (
        corpus_extras.shelfmark_wrap("foo + bar")
        == "<span>foo</span> + <span>bar</span>"
    )
    assert (
        corpus_extras.shelfmark_wrap("foo + bar + baz")
        == "<span>foo</span> + <span>bar</span> + <span>baz</span>"
    )


def test_get_document_label():
    # should not throw an error
    corpus_extras.get_document_label({})
    # should use fallback for unknown shelfmark
    assert (
        corpus_extras.get_document_label({"type": "Unknown type"})
        == "Unknown type: [unknown shelfmark]"
    )
    # should construct correct label in normal circumstances
    assert (
        corpus_extras.get_document_label({"type": "Letter", "shelfmark": "Foo 123"})
        == "Letter: Foo 123"
    )


def test_translate_url(document):
    # should translate requested URL into Hebrew
    ctx = {"request": HttpRequest()}
    ctx["request"].path = document.get_absolute_url()
    assert corpus_extras.translate_url(ctx, "he").startswith("/he/")

    # if a Hebrew version cannot be determined, should return the original URL
    ctx["request"].path = "https://example.com"
    assert corpus_extras.translate_url(ctx, "he") == "https://example.com"


class TestAdminExtrasTemplateTags:
    def test_get_fieldsets_and_inlines(self):
        # mock admin form with fieldsets
        adminform = MagicMock()
        adminform.__iter__.return_value = ("fieldset1", "fieldset2")
        # mock inlines
        inlines = ("inline1", "inline2")

        # mock fieldsets_and_inlines_order
        adminform.model_admin.fieldsets_and_inlines_order = ("f", "i", "f", "itt")

        # should return the first fieldset, then inline, then second fieldset
        fieldsets_and_inlines = admin_extras.get_fieldsets_and_inlines(
            {"adminform": adminform, "inline_admin_formsets": inlines}
        )
        assert fieldsets_and_inlines[0] == ("f", "fieldset1")
        assert fieldsets_and_inlines[1] == ("i", "inline1")
        assert fieldsets_and_inlines[2] == ("f", "fieldset2")

        # should include itt panel entry with None as its second value
        assert fieldsets_and_inlines[3] == ("itt", None)

        # should append the remaining inline at the end
        assert fieldsets_and_inlines[4] == ("i", "inline2")
