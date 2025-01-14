from geniza.corpus.ja import (
    arabic_or_ja,
    arabic_to_ja,
    contains_arabic,
    contains_hebrew,
    ja_to_arabic,
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


def test_contains_hebrew():
    assert not contains_hebrew("my keyword search")
    assert not contains_hebrew("دينار")
    assert contains_hebrew("דינאר mixed with english")
    assert contains_hebrew("mixed מצחף and english")


def test_ja_to_arabic():
    assert ja_to_arabic("דינאר") == "دىنار OR ذىنار OR دينار OR ذينار"
    assert ja_to_arabic("מצחף") == "مصحف OR مضحف"
    assert ja_to_arabic("סנה") == "سنة OR سنه"
    assert ja_to_arabic("טבאךֹ") == "طباكֹ OR ظباكֹ OR طباخֹ OR ظباخֹ"
    assert ja_to_arabic("מ") == "م"
    assert ja_to_arabic("") == ""
    assert ja_to_arabic("english text") == "english text"
    assert ja_to_arabic("دينار") == "دينار"


def test_arabic_or_ja__no_arabic_or_ja():
    txt = "my keyword search"
    # should be unchanged
    assert arabic_or_ja(txt) == txt


def test_arabic_or_ja__arabic():
    # single word — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار", boost=False) == "(دينار OR דינאר)"
    # multiple words — should return match for arabic or judaeo-arabic
    assert arabic_or_ja("دينار مصحف", boost=False) == "(دينار OR דינאר) (مصحف OR מצחף)"
    # mixed english and arabic
    assert arabic_or_ja("help مصحف", boost=False) == "help (مصحف OR מצחף)"
    # with boosting
    assert arabic_or_ja("دينار") == "(دينار^100.0 OR דינאר)"


def test_arabic_or_ja__ja():
    # single word — should return match for arabic or judaeo-arabic
    assert (
        arabic_or_ja("דינאר", boost=False)
        == "(דינאר OR دىنار OR ذىنار OR دينار OR ذينار)"
    )
    # multiple words — should return match for arabic or judaeo-arabic
    assert (
        arabic_or_ja("דינאר מצחף", boost=False)
        == "(דינאר OR دىنار OR ذىنار OR دينار OR ذينار) (מצחף OR مصحف OR مضحف)"
    )
    # mixed english and judaeo-arabic
    assert arabic_or_ja("help מצחף", boost=False) == "help (מצחף OR مصحف OR مضحف)"
    # with boosting
    assert arabic_or_ja("דינאר") == "(דינאר^100.0 OR دىنار OR ذىنار OR دينار OR ذينار)"


def test_arabic_or_ja_exact_phrase():
    # make sure basic exact quote is working
    assert arabic_or_ja('"تعطل شغله"', boost=False) == '("تعطل شغله" OR "תעטל שגלה")'

    # make sure broken quotes are ignored and arabic words are converted
    assert arabic_or_ja('"تعطل شغله', boost=False) == '"(تعطل OR תעטל) (شغله OR שגלה)'

    # to test what would happen if we had 1+ arabic phrases
    # (within quotation marks) and 1+ arabic words (not inside quotes)
    assert (
        arabic_or_ja('"تعطل شغله" etc etc شغله', boost=False)
        == '("تعطل شغله" OR "תעטל שגלה") etc etc (شغله OR שגלה)'
    )

    # proximity
    assert (
        arabic_or_ja('"تعطل شغله"~10', boost=False) == '("تعطل شغله" OR "תעטל שגלה")~10'
    )

    # with boosting
    assert (
        arabic_or_ja("تعطل شغله", boost=True)
        == "(تعطل^100.0 OR תעטל) (شغله^100.0 OR שגלה)"
    )
    assert (
        arabic_or_ja('"تعطل شغله"', boost=True) == '("تعطل شغله"^100.0 OR "תעטל שגלה")'
    )

    # make sure query string is working
    assert (
        arabic_or_ja('transcription:("تعطل شغله") etc etc شغله', boost=False)
        == 'transcription:(("تعطل شغله" OR "תעטל שגלה")) etc etc (شغله OR שגלה)'
    )

    # make sure non-arabic field query is left unchanged
    assert arabic_or_ja('shelfmark:"jrl series a"') == 'shelfmark:"jrl series a"'

    # two phrases with whitespace between quotes; should be ignored
    assert (
        arabic_or_ja('shelfmark:"T-S NS" "he divorced"', boost=False)
        == 'shelfmark:"T-S NS" "he divorced"'
    )
