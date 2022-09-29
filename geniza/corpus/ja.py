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


def tokenize_words_and_phrases(text):
    # Get a list of search query tokens which are each either:
    #    - a phrase (text inside double quotes)
    #    - a word
    return re.findall(r'"[^"]*"|[^ "]*[^ "]', text)


def arabic_or_ja_allowing_phrases(text, boost=True):
    new_terms = [
        (
            f"({arabic_to_ja(word_or_phrase)}|{word_or_phrase})"
            if contains_arabic(word_or_phrase)
            else word_or_phrase
        )
        for word_or_phrase in tokenize_words_and_phrases(text)
    ]
    new_text = " ".join(new_terms)
    new_text = new_text.replace(") )", ")").replace("( (", "(")
    return new_text


def arabic_or_ja(text, boost=True):
    """Convert text to arabic or judaeo-arabic string; boost arabic by default"""
    # if there is no arabic text, return as is
    if not contains_arabic(text):
        return text

    # extract arabic words from the search query

    arabic_words = re_AR_letters.findall(text)
    # generate judaeo-arabic equivalents
    ja_words = [arabic_to_ja(word) for word in arabic_words]
    # iterate over the original and converted words together and combine

    # prob something like this?
    # ja_phrase = arabic_to_ja(text)
    ##

    # add boosting so arabic matches will be more relevant,
    # unless boosting is disabled
    boost = "^2.0" if boost else ""

    for i, arabic_word in enumerate(arabic_words):
        ja_word = ja_words[i]
        # if the words differ, combine them as an OR
        # then replace them in the original search query
        # (preserving any existing search syntax like quotes, wildcards, etc)
        if arabic_word != ja_word:
            ar_or_ja_word = "(%s%s|%s)" % (arabic_word, boost, ja_word)
            text = text.replace(arabic_word, ar_or_ja_word)

    return text
