from unittest.mock import Mock

import pytest
from django.http.request import QueryDict
from piffle.iiif import IIIFImageClient

from geniza.common.utils import absolutize_url
from geniza.corpus.templatetags import corpus_extras
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


def test_iiif_info_json():
    img1 = IIIFImageClient("http://image.server/path/", "myimgid")
    img2 = IIIFImageClient("http://image.server/path/", "myimgid2")
    imgs = [{"image": img1}, {"image": img2}]
    json_ids = corpus_extras.iiif_info_json(imgs)
    # should contain the same ids but with /info.json appended
    assert "http://image.server/path/myimgid/info.json" in json_ids
    assert "http://image.server/path/myimgid2/info.json" in json_ids


def test_h1_to_h3():
    html = "<div><h1>hi</h1><h3>hello</h3></div>"
    assert corpus_extras.h1_to_h3(html) == "<div><h3>hi</h3><h3>hello</h3></div>"


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
