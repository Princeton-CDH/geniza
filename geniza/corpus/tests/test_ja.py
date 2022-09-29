from operator import contains

from geniza.corpus.ja import (  # extract_arabic_phrases,; extract_arabic_words,; extract_arabic_words_outside_phrases,; extract_quoted_phrases,; locate_quoted_phrases,
    arabic_or_ja,
    arabic_or_ja_allowing_phrases,
    arabic_to_ja,
    contains_arabic,
    tokenize_words_and_phrases,
)


def test_contains_arabic():
    assert not contains_arabic("my keyword search")
    assert contains_arabic("دينار")
    assert contains_arabic("مصحف mixed with english")
    assert contains_arabic(" mixed مصحف and english")


def test_arabic_to_ja():
    assert arabic_to_ja("دينار") == "דינאר"
    assert arabic_to_ja("مصحف") == "מצחף"
    assert arabic_to_ja("سنة") == "סנה"
    assert arabic_to_ja("طباخ") == "טבאךֹ"
    assert arabic_to_ja("") == ""
    assert arabic_to_ja("english text") == "english text"


def test_arabic_or_ja__no_arabic():
    txt = "my keyword search"
    # should be unchanged
    assert arabic_or_ja(txt) == txt


def test_arabic_or_ja__arabic():
    # single word — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار", boost=False) == "(دينار|דינאר)"
    # multiple words — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار مصحف", boost=False) == "(دينار|דינאר) (مصحف|מצחף)"
    # mixed english and arabic
    assert arabic_or_ja("help مصحف", boost=False) == "help (مصحف|מצחף)"
    # with boosting
    assert arabic_or_ja("دينار") == "(دينار^2.0|דינאר)"


def test_arabic_or_ja_exact_phrase():
    # make sure basic or is working
    assert (
        arabic_or_ja_allowing_phrases('"تعطل شغله"', boost=False)
        == '("תעטל שגלה"|"تعطل شغله")'
    )

    # make sure broken quotes still work
    assert arabic_or_ja_allowing_phrases('"تعطل شغله', boost=False) in {
        "(شغله|שגלה) (تعطل|תעטל)",
        "(تعطل|תעטל) (شغله|שגלה)",
        "(שגלה|شغله) (תעטל|تعطل)",
        "(תעטל|تعطل) (שגלה|شغله)",
    }

    # need to test what would happen if we had 1+ arabic phrases (within quotation marks) and 1+ arabic words (not inside quotes)
    assert arabic_or_ja_allowing_phrases('"تعطل شغله" etc etc شغله', boost=False) in {
        '("תעטל שגלה"|"تعطل شغله") etc etc (شغله|שגלה)',
        '("תעטל שגלה"|"تعطل شغله") etc etc (שגלה|شغله)',
    }

    # proximity
    # @TODO assert arabic_or_ja('"تعطل شغله"~10', boost=False) == '"(تعطل|תעטל) (شغله|שגלה)"~10'
    # with boosting
    # @TODO assert arabic_or_ja('"تعطل شغله"') == '"(تعطل^2.0|תעטל) (شغله^2.0|שגלה)"'

    # make sure query string is working
    assert (
        arabic_or_ja_allowing_phrases('transcription:("تعطل شغله"')
        == """transcription:("תעטל שגלה"|"تعطل شغله")"""
    )


def test_tokenize_words_and_phrases():
    assert tokenize_words_and_phrases(
        'He said "hello world" and "goodbye world" and "goodbye'
    ) == ["He", "said", '"hello world"', "and", '"goodbye world"', "and", "goodbye"]
