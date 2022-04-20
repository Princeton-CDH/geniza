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
re_AR_letters = re.compile(r"[\u0600-\u06FF]")


def contains_arabic(text):
    # check if the text contains any arabic letters
    return re_AR_letters.search(text)


re_he_final_letters = re.compile(r"(%s)$" % "|".join(he_final_letters.keys()))


def ar_word_to_ja(word):
    # don't process empty string; just return
    if not word:
        return word
    # for a single word
    ja_word = word.translate(arabic_to_ja_table).strip()
    # convert last letter to final form if necessary
    # needs to use regex to handle accented characters, which complicate last letter indexing
    return re.sub(re_he_final_letters, lambda m: he_final_letters[m.group(0)], ja_word)


def arabic_to_ja(text):
    # handle multiple words
    # if there is no arabic text, return as is
    if not contains_arabic(text):
        return text

    # if there is arabic, split into words and make a pattern
    return " ".join([ar_word_to_ja(word) for word in re.split(r"\s+", text)])


def arabic_or_ja(text):
    # if there is no arabic text, return as is
    if not contains_arabic(text):
        return text

    # if there is arabic, split into words and make a pattern
    words = re.split(r"\s+", text)
    ja_words = [ar_word_to_ja(word) for word in words]
    search_words = []
    for word, ja_word in dict(zip(words, ja_words)).items():
        # if the words differ, combine them as an OR
        if word != ja_word:
            search_words.append("(%s|%s)" % (word, ja_word))
        # otherwise, just return the one word
        else:
            search_words.append(word)
    # combine them back into the search string
    return " ".join(search_words)
