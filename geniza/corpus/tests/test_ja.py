from operator import contains

from geniza.corpus.ja import arabic_or_ja, arabic_to_ja, contains_arabic


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
    assert arabic_or_ja("دينار") == "(دينار|דינאר)"
    # multiple words — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار مصحف") == "(دينار|דינאר) (مصحف|מצחף)"
    # mixed english and arabic
    assert arabic_or_ja("help مصحف") == "help (مصحف|מצחף)"


def test_arabic_or_ja_exact_phrase():
    assert arabic_or_ja('"تعطل شغله"') == '"(تعطل|תעטל) (شغله|שגלה)"'
    # proximity
    assert arabic_or_ja('"تعطل شغله"~10') == '"(تعطل|תעטל) (شغله|שגלה)"~10'
