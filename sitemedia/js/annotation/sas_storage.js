// annotorious plugin to use simple annotation server as a storage

import { _ } from "core-js";
import SimpleAnnotationServerV2Adapter from "./SimpleAnnotationServerV2Adapter";

// const AnnotationServerStorage = (client, serverConfig, settings) => {
const AnnotationServerStorage = (anno, settings) => {
    let adapter = new SimpleAnnotationServerV2Adapter(
        settings.target, // should be canvas id
        settings.annotationEndpoint
    );

    // load and display annotations from server
    adapter.all().then((annotationPage) => {
        anno.setAnnotations(annotationPage.items);
    });

    // Lifecycle event handlers
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

    // TODO handle update
    // client.on("updateAnnotation", (annotation, previous) => {
    //     console.log(annotation);
    //     console.log(previous);
    //     // POST to /annotation/update
    //     // The posted annotation should have an @id which exists in the store

    //     /*findById(previous.id)
    //       .then(doc => doc.ref.update(annotation))
    //       .catch(error => console.log('Error updating annotation', error, previous, annotation))*/
    // });

    anno.on("deleteAnnotation", (annotation) => {
        adapter.delete(annotation.id);
    });
};

export default AnnotationServerStorage;
