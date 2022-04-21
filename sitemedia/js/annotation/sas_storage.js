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

    function adjustTargetSource(target) {
        // annotorious sets the target as a string id;
        // we need to structure it to add canvas/manifest info
        if (typeof target.source == "string") {
            // add manifest id to annotation
            target.source = {
                // use the configured target (should be canvas id)
                id: settings.target,
                // link to containing manifest
                partOf: {
                    id: settings.manifest,
                },
            };
        }
    }

    // create a new annotation
    anno.on("createAnnotation", async (annotation) => {
        adjustTargetSource(annotation.target);
        adapter.create(annotation).then((resp) => {
            // by default, storage reloads all annotations for this page;
            // signal that annotations have been loaded
            document.dispatchEvent(AnnoLoadEvent);
        });
        // how to update id for annotorious?
        anno.addAnnotation(annotation);
        return annotation;
    });

    // update an annotation
    anno.on("updateAnnotation", (annotation, previous) => {
        // The posted annotation should have an @id which exists in the store
        let newId = annotation.id; // do we need to do anything with this?
        annotation.id = previous.id;
        // target needs to be updated if the image selection has changed
        adjustTargetSource(annotation.target);
        adapter.update(annotation);
        // add the annotation to annotorious again to make sure the display is up to date
        anno.addAnnotation(annotation);
    });

    // delete an annotation
    anno.on("deleteAnnotation", (annotation) => {
        adapter.delete(annotation.id);
    });

    const storagePlugin = {
        adapter: adapter,
    };

    return storagePlugin;
};

export default AnnotationServerStorage;
