"""Local utilities for creating IIIF manifests and annotation lists"""

from attrdict import AttrMap
from django.core.serializers.json import DjangoJSONEncoder
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
    "resources": [],
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
        if isinstance(obj, AttrMap):
            return dict(obj)
        return super().default(obj)
