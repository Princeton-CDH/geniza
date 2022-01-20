from asyncio import format_helpers
from unittest.mock import Mock
from urllib import parse

import pytest
from django.http.request import QueryDict

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


def test_footnotes_on_source(document, join, source, twoauthor_source):
    # Create two footnotes linking a certain document and source
    fn = Footnote.objects.create(
        content_object=document,
        source=source,
        doc_relation=Footnote.EDITION,
    )
    fn2 = Footnote.objects.create(
        content_object=document,
        source=source,
        doc_relation={Footnote.EDITION, Footnote.TRANSLATION},
        content="some text",
    )

    # Link source but not document
    fn_source_not_doc = Footnote.objects.create(
        content_object=join,
        source=source,
        doc_relation=Footnote.DISCUSSION,
    )

    # Link document but not source
    fn_doc_not_source = Footnote.objects.create(
        content_object=document,
        source=twoauthor_source,
        doc_relation=Footnote.DISCUSSION,
    )

    fos = corpus_extras.footnotes_on_source(document, source)
    # Should get all footnotes on the passed document and source
    assert fn in fos
    assert fn2 in fos

    # Should not get a footnote on the source alone, or document alone
    assert fn_source_not_doc not in fos
    assert fn_doc_not_source not in fos


def test_unique_relations_on_source(document, source):
    # Create a footnotes linking a certain document and source as EDITION
    Footnote.objects.create(
        content_object=document,
        source=source,
        doc_relation=Footnote.EDITION,
    )
    # Create a footnotes linking a certain document and source as EDITION, TRANSLATION
    Footnote.objects.create(
        content_object=document,
        source=source,
        doc_relation={Footnote.EDITION, Footnote.TRANSLATION},
        content="some text",
    )

    assert (
        corpus_extras.unique_relations_on_source(document, source)
        == "Edition, Translation"
    )
