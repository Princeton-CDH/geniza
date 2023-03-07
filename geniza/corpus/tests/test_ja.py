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
    assert arabic_or_ja("دينار", boost=False) == "(دينار|דינאר)"
    # multiple words — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار مصحف", boost=False) == "(دينار|דינאר) (مصحف|מצחף)"
    # mixed english and arabic
    assert arabic_or_ja("help مصحف", boost=False) == "help (مصحف|מצחף)"
    # with boosting
    assert arabic_or_ja("دينار") == "(دينار^2.0|דינאר)"


def test_arabic_or_ja_exact_phrase():
    # make sure basic exact quote is working
    assert arabic_or_ja('"تعطل شغله"', boost=False) == '("تعطل شغله"|"תעטל שגלה")'

    # make sure broken quotes are ignored and arabic words are converted
    assert arabic_or_ja('"تعطل شغله', boost=False) == '"(تعطل|תעטל) (شغله|שגלה)'

    # to test what would happen if we had 1+ arabic phrases
    # (within quotation marks) and 1+ arabic words (not inside quotes)
    assert (
        arabic_or_ja('"تعطل شغله" etc etc شغله', boost=False)
        == '("تعطل شغله"|"תעטל שגלה") etc etc (شغله|שגלה)'
    )

    # proximity
    assert arabic_or_ja('"تعطل شغله"~10', boost=False) == '("تعطل شغله"|"תעטל שגלה")~10'

    # with boosting
    assert arabic_or_ja("تعطل شغله", boost=True) == "(تعطل^2.0|תעטל) (شغله^2.0|שגלה)"
    assert arabic_or_ja('"تعطل شغله"', boost=True) == '("تعطل شغله"^2.0|"תעטל שגלה")'

    # make sure query string is working
    assert (
        arabic_or_ja('transcription:("تعطل شغله") etc etc شغله', boost=False)
        == 'transcription:(("تعطل شغله"|"תעטל שגלה")) etc etc (شغله|שגלה)'
    )

    # make sure non-arabic field query is left unchanged
    assert arabic_or_ja('shelfmark:"jrl series a"') == 'shelfmark:"jrl series a"'

    # two phrases with whitespace between quotes; should be ignored
    assert (
        arabic_or_ja('shelfmark:"T-S NS" "he divorced"', boost=False)
        == 'shelfmark:"T-S NS" "he divorced"'
    )
