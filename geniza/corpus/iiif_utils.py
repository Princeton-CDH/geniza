"""Local utilities for creating IIIF manifests and annotation lists"""

from piffle.presentation import IIIFPresentation

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


def part_of(manifest_id, label):
    # create the "partOf" structure given an id and label
    return [
        {
            "@id": str(manifest_id),
            "@type": "sc:Manifest",
            "label": {"en": [str(label)]},
        }
    ]
