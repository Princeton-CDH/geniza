import pytest

from geniza.corpus.templatetags import corpus_extras


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
    assert corpus_extras.dict_item({13: 7}, 13) is 7
