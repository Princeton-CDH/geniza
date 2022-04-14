from operator import contains

from geniza.corpus.ja import ar_word_to_ja, arabic_or_ja, contains_arabic


def test_contains_arabic():
    assert not contains_arabic("my keyword search")
    assert contains_arabic("دينار")
    assert contains_arabic("مصحف mixed with english")
    assert contains_arabic(" mixed مصحف and english")


def test_ar_word_to_ja():
    assert ar_word_to_ja("دينار") == "דיהאר"
    assert ar_word_to_ja("مصحف") == "מצחף"
    assert ar_word_to_ja("سنة") == "סהה"


def test_arabic_or_ja__no_arabic():
    txt = "my keyword search"
    # should be unchanged
    assert arabic_or_ja(txt) == txt


def test_arabic_or_ja__arabic():
    # single word — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار") == "(دينار|דיהאר)"
    # multiple words — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار مصحف") == "(دينار|דיהאר) (مصحف|מצחף)"
    # mixed english and arabic
    assert arabic_or_ja("help مصحف") == "help (مصحف|מצחף)"
