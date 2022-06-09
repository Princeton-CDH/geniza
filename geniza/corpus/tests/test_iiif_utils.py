from django.utils.translation import activate

from geniza.corpus.iiif_utils import get_iiif_string


def test_get_iiif_string():
    # plain string
    assert get_iiif_string("text") == "text"
    # language-labeled values
    language_vals = [
        {"@language": "de", "@value": "Universitätsbibliothek Heidelberg"},
        {"@language": "en", "@value": "Heidelberg University Library"},
    ]
    # make sure english is active language
    activate("en")
    assert get_iiif_string(language_vals) == "Heidelberg University Library"

    # try with an unavailable language, should fall back to English
    activate("he")
    assert get_iiif_string(language_vals) == "Heidelberg University Library"

    # no english available, should choose first option
    language_vals = [{"@language": "de", "@value": "Universitätsbibliothek Heidelberg"}]
    assert get_iiif_string(language_vals) == "Universitätsbibliothek Heidelberg"
