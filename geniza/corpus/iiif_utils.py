"""Local utilities for creating IIIF manifests and annotation lists"""

from addict import Dict
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import get_language
from djiffy.importer import ManifestImporter
from piffle.presentation import IIIFPresentation

from geniza.common.utils import absolutize_url

# some of this could make sense to add to piffle,
# but let's develop it within this projet for now

# starting point for an empty manifest
base_manifest = {
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@type": "sc:Manifest",
    "viewingDirection": "left-to-right",
    "attribution": "",
}


def new_iiif_manifest():
    return IIIFPresentation(base_manifest.copy())


base_annotation_list = {
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@type": "sc:AnnotationList",
}


def new_annotation_list():
    # create outer annotation list structure
    # this is not strictly a presentation object, but
    # the behavior is useful (@context, @id, attrdict)
    return IIIFPresentation(base_annotation_list.copy())


# starting point for an empty canvas
base_canvas = {
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@type": "sc:Canvas",
}


def new_iiif_canvas():
    # create IIIF canvas structure
    return IIIFPresentation(base_canvas.copy())


# try using a generic empty canvas id
EMPTY_CANVAS_ID = "/iiif/canvas/empty/"


def empty_iiif_canvas():
    canvas = new_iiif_canvas()
    canvas.id = absolutize_url(EMPTY_CANVAS_ID)
    # set sizes (these are arbitrary)
    canvas.width = 3200
    canvas.height = 4000
    canvas.label = "image unavailable"
    return canvas


class AttrDictEncoder(DjangoJSONEncoder):
    # make attrdict json-serializable
    def default(self, obj):
        if isinstance(obj, Dict):
            return dict(obj)
        return super().default(obj)


def get_iiif_string(obj):
    """Handle iiif values which may be a single string or maybe a list of language-specific strings"""

    # this should maybe be part of piffle or djiffy; consider moving later;
    # helpful to have django current language logic

    # if it's just a string, return it
    if isinstance(obj, str):
        return obj
    # if it's a list of values with language codes, return the best option
    elif isinstance(obj, list) and "@language" in obj[0]:
        # convert into a language-value dictionary for easy lookup
        # NOTE: spec is more complicated than this, could be en-latn or similar.
        # Handle with simple case for now
        lang_val = {i["@language"]: i["@value"] for i in obj}
        # return the value for the current django language
        lang = get_language()
        val = lang_val.get(lang, None)
        # if no value for current language and it is not english, try english next
        if not val and lang != "en":
            val = lang_val.get("en", None)

        # if we didn't find a value for current language or english, return the first value
        return val or obj[0]["@value"]
    # if it's a list of strings, return the first value
    elif isinstance(obj, list) and obj and isinstance(obj[0], str):
        return obj[0]


class GenizaManifestImporter(ManifestImporter):
    """Extend :class:`djiffy.importer.ManifestImporter` to customize
    canvas id logic for remixed PGP manifests."""

    def canvas_short_id(self, canvas):
        """Revise default canvas short id logic. Bcause we are remixing
        Manchester canvases, the default behavior which uses the last
        portion of the canvas id, does not result in unique id
        within the manifest (repeated c1 ids). Revise for those
        URLs only to use more of the URI, including the item/manifest id
        to guarantee uniqueness."""

        # use uri portion starting with manchester manifest id
        if "Manchester" in canvas.id:
            return canvas.id.rsplit("servlet/iiif/m/", 1)[1].replace("/", "-")

        # otherwise, use default behavior
        return super().canvas_short_id(canvas)
