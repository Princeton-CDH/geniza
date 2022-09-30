import re

COMPILED_ARABIC_WORDS_OR_PHRASES = re.compile(r'"[ \u0600-\u06FF]+"|[\u0600-\u06FF]+')


# character mapping from a table in Marina Rustow's
# How to read Judaeo-Arabic manuscripts
arabic_ja_chars = {
    "ا": "א",
    "ب": "ב",
    "ت": "ת",
    "ث": "תֹ",
    "ج": "ג",  # גֹ or ג
    "ح": "ח",
    "خ": "כֹ",  # (final form: ֹך)
    "د": "ד",
    "ذ": "דֹ",
    "ر": "ר",
    "ز": "ז",
    "س": "ס",
    "ش": "ש",
    "ص": "צ",  # (final form: ץ)
    "ض": "צ",
    "ط": "ט",
    "ظ": "טֹ",
    "ع": "ע",
    "غ": "ג",  # ג or ֹ ג
    "ف": "פ",  # (final form: ף)
    "ق": "ק",
    "ك": "כ",  # (final form: ך)
    "ل": "ל",
    "م": "מ",  # (final form: ם)
    "ن": "נ",  # (final form: ן)
    "ة": "ה",  # ن or ة
    "ه": "ה",
    "و": "ו",
    "ي": "י",  # ي or ى
    "ى": "י",
    "ئ": "י",
    "ؤ": "ו",
    "أ": "א",
    "آ": "א",
    "ء": "",  # ignore
}

he_final_letters = {
    "כֹ": "ך",
    "צ": "ץ",
    "פ": "ף",
    "כ": "ך",
    "מ": "ם",
    "נ": "ן",
}

# iso codes are AR and JRB if we want to use those

# generate translation tables
arabic_to_ja_table = str.maketrans(arabic_ja_chars)

# regex for range of arabic letters
re_AR_letters = re.compile(r"[\u0600-\u06FF]+")


def contains_arabic(text):
    # check if the text contains any arabic letters
    return re_AR_letters.search(text)


# regex for hebrew letters that have final form; matches on occurrence before word boundary
re_he_final_letters = re.compile(r"(%s)\b" % "|".join(he_final_letters.keys()))


def arabic_to_ja(text):
    # handle multiple words
    # if there is no arabic text, return as is
    if not contains_arabic(text):
        return text

    text = text.translate(arabic_to_ja_table).strip()
    # convert last letter to final form if necessary
    # needs to use regex to handle accented characters, which complicate last letter indexing
    return re.sub(re_he_final_letters, lambda m: he_final_letters[m.group(0)], text)


def arabic_or_ja(text, boost=True):
    # get compiled object
    sr = COMPILED_ARABIC_WORDS_OR_PHRASES

    # find matches
    arabic_wordphrases = sr.findall(text)

    # find what surrounds matches
    nonarabic_wordphrases = sr.split(text)

    # rewrite matches
    arabic_or_ja_wordphrases = [
        f"({arabic_wordphrase}{'^2.0' if boost else ''}|{arabic_to_ja(arabic_wordphrase)})"
        for arabic_wordphrase in arabic_wordphrases
    ]

    # stitch back together
    from itertools import zip_longest

    tokens = [
        tok
        for toks in zip_longest(nonarabic_wordphrases, arabic_or_ja_wordphrases)
        for tok in toks
        if tok
    ]
    return "".join(tokens)
