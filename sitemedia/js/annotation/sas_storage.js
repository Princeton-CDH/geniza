// annotorious plugin to use simple annotation server as a storage

import { _ } from "core-js";
import SimpleAnnotationServerV2Adapter from "./SimpleAnnotationServerV2Adapter";

// define a custom event to indicate that annotations have been loaded
const AnnoLoadEvent = new Event("annotations-loaded");

// const AnnotationServerStorage = (client, serverConfig, settings) => {
const AnnotationServerStorage = (anno, settings) => {
    let adapter = new SimpleAnnotationServerV2Adapter(
        settings.target, // should be canvas id
        settings.annotationEndpoint
    );

    // load and display annotations from server
    adapter.all().then((annotationPage) => {
        anno.setAnnotations(annotationPage.items);
        document.dispatchEvent(AnnoLoadEvent);
    });

    // create a new annotation
    anno.on("createAnnotation", async (annotation) => {
        let target_source = annotation.target.source;
        // add manifest id to annotation
        annotation.target.source = {
            // TODO convert from iiif image to canvas id
            id: settings.target, // target_source,
            // link to containing manifest
            partOf: {
                id: settings.manifest,
            },
        };
        adapter.create(annotation).then((resp) => {
            console.log("createAnnotation: " + resp);
        });
        // how to update id for annotorious?
        return annotation;
    });

    // update an annotation
    anno.on("updateAnnotation", (annotation, previous) => {
        // The posted annotation should have an @id which exists in the store
        let newId = annotation.id; // do we need to do anything with this?
        annotation.id = previous.id;
        adapter.update(annotation);

        // add the annotation to annotorious again to make sure the display is up to date
        anno.addAnnotation(annotation);
    });

    // delete an annotation
    anno.on("deleteAnnotation", (annotation) => {
        adapter.delete(annotation.id);
    });
};

export default AnnotationServerStorage;
