from unittest.mock import Mock

from addict import Dict
from django.utils.translation import activate

from geniza.corpus.iiif_utils import (
    AttrDictEncoder,
    GenizaManifestImporter,
    get_iiif_string,
)


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

    # list of strings, should return first string
    assert get_iiif_string(["text", "test"]) == "text"


def test_manifestimporter_canvas_id():
    jrl_canvas = Mock(
        id="https://example.co/servlet/iiif/m/ManchesterDev~95~2~25450~111734/canvas/c1"
    )

    gmi = GenizaManifestImporter()
    # new behavior
    assert (
        gmi.canvas_short_id(jrl_canvas) == "ManchesterDev~95~2~25450~111734-canvas-c1"
    )

    canvas = Mock(id="https://example.co/iiif/c12345")
    assert gmi.canvas_short_id(canvas) == "c12345"


def test_convert_attrdict():
    # should convert addict Dict into python dict
    attrdict = Dict({"key": "value"})
    assert attrdict.key == "value"
    encoder = AttrDictEncoder()
    new_dict = encoder.default(attrdict)
    assert new_dict["key"] == "value"
