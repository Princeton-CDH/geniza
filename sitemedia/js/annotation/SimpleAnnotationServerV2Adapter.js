/* Convert between v2 (open annotation) and v3 (w3c) annotations
   in order to bridge between annotorious (w3c) and simple annotation server (v2).

   Adapted from mirador-annotations code
   https://github.com/ProjectMirador/mirador-annotations/blob/master/src/SimpleAnnotationServerV2Adapter.js

*/
export default class SimpleAnnotationServerV2Adapter {
    /** */
    constructor(canvasId, endpointUrl) {
        this.canvasId = canvasId;
        this.endpointUrl = endpointUrl;
    }

    /** */
    get annotationPageId() {
        return `${this.endpointUrl}/search?uri=${this.canvasId}`;
    }

    /** */
    async create(annotation) {
        return fetch(`${this.endpointUrl}/create`, {
            body: JSON.stringify(
                SimpleAnnotationServerV2Adapter.createV2Anno(annotation)
            ),
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            method: "POST",
        })
            .then((response) => {
                return this.all();
            })
            .catch(() => this.all());
    }

    /** */
    async update(annotation) {
        return fetch(`${this.endpointUrl}/update`, {
            body: JSON.stringify(
                SimpleAnnotationServerV2Adapter.createV2Anno(annotation)
            ),
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            method: "POST",
        })
            .then((response) => this.all())
            .catch(() => this.all());
    }

    /** */
    async delete(annoId) {
        return fetch(
            `${this.endpointUrl}/destroy?uri=${encodeURIComponent(annoId)}`,
            {
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                method: "DELETE",
            }
        )
            .then((response) => this.all())
            .catch(() => this.all());
    }

    /** */
    async get(annoId) {
        // SAS does not have GET for a single annotation
        const annotationPage = await this.all();
        if (annotationPage) {
            return annotationPage.items.find((item) => item.id === annoId);
        }
        return null;
    }

    /** Returns an AnnotationPage with all annotations */
    async all() {
        const resp = await fetch(this.annotationPageId);
        const annos = await resp.json();
        return this.createAnnotationPage(annos);
    }

    /** Creates a V2 annotation from a V3 annotation */
    static createV2Anno(v3anno) {
        const v2anno = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "@type": "oa:Annotation",
            motivation: "oa:commenting", // todo use v3anno.motivation
            on: {
                "@type": "oa:SpecificResource",
                full: v3anno.target.source.id,
            },
        };
        // copy id if it is SAS-generated
        if (v3anno.id && v3anno.id.startsWith("http")) {
            v2anno["@id"] = v3anno.id;
        }
        if (Array.isArray(v3anno.body)) {
            v2anno.resource = v3anno.body.map((b) => this.createV2AnnoBody(b));
        } else {
            v2anno.resource = this.createV2AnnoBody(v3anno.body);
        }
        if (v3anno.target.selector) {
            if (Array.isArray(v3anno.target.selector)) {
                const selectors = v3anno.target.selector.map((s) =>
                    this.createV2AnnoSelector(s)
                );
                // create choice, assuming two elements and 0 is default
                v2anno.on.selector = {
                    "@type": "oa:Choice",
                    default: selectors[0],
                    item: selectors[1],
                };
            } else {
                v2anno.on.selector = this.createV2AnnoSelector(
                    v3anno.target.selector
                );
            }
            if (v3anno.target.source.partOf) {
                v2anno.on.within = {
                    "@id": v3anno.target.source.partOf.id,
                    "@type": "sc:Manifest",
                };
            }
        }
        return v2anno;
    }

    /** */
    static createV2AnnoBody(v3body) {
        const v2body = {
            chars: v3body.value,
        };
        if (v3body.purpose === "tagging") {
            v2body["@type"] = "oa:Tag";
        } else {
            v2body["@type"] = "dctypes:Text";
        }
        if (v3body.format) {
            v2body.format = v3body.format;
        }
        if (v3body.language) {
            v2body.language = v3body.language;
        }
        return v2body;
    }

    /** */
    static createV2AnnoSelector(v3selector) {
        switch (v3selector.type) {
            case "SvgSelector":
                return {
                    "@type": "oa:SvgSelector",
                    value: v3selector.value,
                };
            case "FragmentSelector":
                return {
                    "@type": "oa:FragmentSelector",
                    // SAS uses location in xywh=x,y,w,h format; annotorious uses pixel:x,y,w,h
                    value: v3selector.value.replace("xywh=pixel:", "xywh="),
                };
            default:
                return null;
        }
    }

    /** Creates an AnnotationPage from a list of V2 annotations */
    createAnnotationPage(v2annos) {
        if (Array.isArray(v2annos)) {
            const v3annos = v2annos.map((a) =>
                SimpleAnnotationServerV2Adapter.createV3Anno(a)
            );
            return {
                id: this.annotationPageId,
                items: v3annos,
                type: "AnnotationPage",
            };
        }
        return v2annos;
    }

    /** Creates a V3 annotation from a V2 annotation */
    static createV3Anno(v2anno) {
        const v3anno = {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            id: v2anno["@id"],
            motivation: "commenting",
            type: "Annotation",
        };
        if (Array.isArray(v2anno.resource)) {
            v3anno.body = v2anno.resource.map((b) => this.createV3AnnoBody(b));
        } else {
            v3anno.body = this.createV3AnnoBody(v2anno.resource);
        }
        let v2target = v2anno.on;
        if (Array.isArray(v2target)) {
            [v2target] = v2target;
        }
        v3anno.target = {
            selector: this.createV3AnnoSelector(v2target.selector),
            source: v2target.full,
        };
        if (v2target.within) {
            v3anno.target.source = {
                id: v2target.full,
                partOf: {
                    id: v2target.within["@id"],
                    type: "Manifest",
                },
                type: "Canvas",
            };
        }
        return v3anno;
    }

    /** */
    static createV3AnnoBody(v2body) {
        const v3body = {
            type: "TextualBody",
            value: v2body.chars,
        };
        if (v2body.format) {
            v3body.format = v2body.format;
        }
        if (v2body.language) {
            v3body.language = v2body.language;
        }
        if (v2body["@type"] === "oa:Tag") {
            v3body.purpose = "tagging";
        }
        return v3body;
    }

    /** */
    static createV3AnnoSelector(v2selector) {
        switch (v2selector["@type"]) {
            case "oa:SvgSelector":
                return {
                    type: "SvgSelector",
                    value: v2selector.value,
                };
            case "oa:FragmentSelector":
                return {
                    type: "FragmentSelector",
                    conformsTo: "http://www.w3.org/TR/media-frags/",
                    // SAS returns location in xywh=x,y,w,h format; annotorious uses pixel:x,y,w,h
                    value: v2selector.value.replace("xywh=", "xywh=pixel:"),
                };
            case "oa:Choice":
                /* create alternate selectors */
                return [
                    this.createV3AnnoSelector(v2selector.default),
                    this.createV3AnnoSelector(v2selector.item),
                ];
            default:
                return null;
        }
    }
}
