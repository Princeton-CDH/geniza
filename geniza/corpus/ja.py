import itertools
import re

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

ja_arabic_chars = {
    "א": "ا",
    "ב": "ب",
    "ג": ["غ", "ج"],
    "ג̇": ["غ", "ج"],
    "ד": ["د", "ذ"],
    "ד̇": ["د", "ذ"],
    "ה": ["ة", "ه"],
    "ו": "و",
    "ז": "ز",
    "ח": "ح",
    "ט": ["ط", "ظ"],
    "ט̇": ["ط", "ظ"],
    "י": ["ى", "ي"],
    "ך": ["ك", "خ"],
    "ך̇": ["ك", "خ"],
    "כ": ["ك", "خ"],
    "כ̇": ["ك", "خ"],
    "ל": "ل",
    "ם": "م",
    "מ": "م",
    "ן": "ن",
    "נ": "ن",
    "ס": "س",
    "ע": "ع",
    "ף": "ف",
    "פ": "ف",
    "ץ": ["ص", "ض"],
    "ץ̇": ["ص", "ض"],
    "צ": ["ص", "ض"],
    "צ̇": ["ص", "ض"],
    "ק": "ق",
    "ר": "ر",
    "ש": "ش",
    "ת": ["ت", "ث"],
    "ת̇": ["ت", "ث"],
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
    # handle multiple words, translate from arabic to ja
    text = text.translate(arabic_to_ja_table).strip()
    # convert last letter to final form if necessary
    # needs to use regex to handle accented characters, which complicate last letter indexing
    return re.sub(re_he_final_letters, lambda m: he_final_letters[m.group(0)], text)


# regex for range of hebrew letters
re_HE_letters = re.compile(r"[\u0590-\u05fe]+")


def contains_hebrew(text):
    # check if the text contains any hebrew letters
    return re_HE_letters.search(text)


def ja_to_arabic(text):
    # handle multiple words, translate from ja to arabic

    # we can't use translate() because there are sometimes multiple options for
    # the arabic translation, due to hebrew having fewer letters in its alphabet
    for k, v in ja_arabic_chars.items():
        if type(v) == list and k in text:
            # list means there is more than one option, so join translations with OR
            texts = []
            for option in v:
                texts.append(re.sub(k, option, text))
            text = " OR ".join(texts)
        elif type(v) == str:
            # only one possible translation
            text = re.sub(k, v, text)

    return text.strip()


def make_translingual(text, boost, pattern, trans_func):
    # find matching tokens by regex
    matching_wordphrases = pattern.findall(text)

    # get everything surrounding the matches
    nonmatching_wordphrases = pattern.split(text)

    # rewrite phrasematches using translingual function, boost, and OR query
    translingual_wordphrases = [
        f"({wordphrase}{'^2.0' if boost else ''} OR {trans_func(wordphrase)})"
        for wordphrase in matching_wordphrases
    ]

    # stitch the search query back together:
    # pair tokens surrounding matching terms with the terms they were split on,
    # fill any missing values with empty strings, and merge it all into a single string
    return "".join(
        itertools.chain.from_iterable(
            (
                itertools.zip_longest(
                    nonmatching_wordphrases, translingual_wordphrases, fillvalue=""
                )
            )
        )
    )


# regex to find hebrew word, or exact phrase with only hebrew + whitepace
re_HE_WORD_OR_PHRASE = re.compile(
    r'"[\u0590-\u05fe]+[\s\u0590-\u05fe]*"|[\u0590-\u05fe]+'
)

# regex to find arabic word or exact phrase with only arabic + whitepace
re_AR_WORD_OR_PHRASE = re.compile(
    r'"[\u0600-\u06FF]+[\s\u0600-\u06FF]*"|[\u0600-\u06FF]+'
)


def arabic_or_ja(text, boost=True):
    if not contains_hebrew(text) and not contains_arabic(text):
        return text
    texts = []
    if contains_hebrew(text):
        texts.append(make_translingual(text, boost, re_HE_WORD_OR_PHRASE, ja_to_arabic))
    if contains_arabic(text):
        texts.append(make_translingual(text, boost, re_AR_WORD_OR_PHRASE, arabic_to_ja))
    return f"({' OR '.join(texts)})" if len(texts) > 1 else texts[0]
