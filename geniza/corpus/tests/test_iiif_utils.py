import os
from unittest.mock import Mock

import pytest
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

    # penn canvas ids end with /canvas
    penn_canvas = Mock(
        id="https://digitalrepository.library.upenn.edu/iiif/2/assets/d7c9082e-76d1-4c4e-97eb-25baf0406fa5/canvas"
    )
    assert gmi.canvas_short_id(penn_canvas) == "d7c9082e-76d1-4c4e-97eb-25baf0406fa5"


@pytest.mark.django_db
def test_manifestimporter_penn_manifest():
    # penn manifest; canvas ids all end with /canvas
    fixture = os.path.join(
        os.path.dirname(__file__), "fixtures", "penn_halper_337_manifest.json"
    )

    # should not encounter duplicate canvas short id IntegrityError
    manifest = GenizaManifestImporter().import_paths([fixture])[0]
    canvases = manifest.canvases.all()
    assert canvases.count() == 2
    assert [c.short_id for c in canvases] == [
        "d7c9082e-76d1-4c4e-97eb-25baf0406fa5",
        "c117ca7f-66d2-42ca-b847-22f3c99637e1",
    ]
    assert canvases[0].iiif_image_id == (
        "https://iiif-images.library.upenn.edu/iiif/2/d7c9082e-76d1-4c4e-97eb-25baf0406fa5"
    )


def test_convert_attrdict():
    # should convert addict Dict into python dict
    attrdict = Dict({"key": "value"})
    assert attrdict.key == "value"
    encoder = AttrDictEncoder()
    new_dict = encoder.default(attrdict)
    assert new_dict["key"] == "value"
