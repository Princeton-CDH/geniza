// annotorious plugin to use simple annotation server as a storage

import { _ } from "core-js";

const annotationStub = {
    "@context": "http://www.w3.org/ns/anno.jsonld",
    type: "Annotation",
    // 'body': []
};

function toW3CAnnotation(oa_data) {
    // basic conversion from open annotation to w3c annotation

    let annotation = { ...annotationStub };
    // convert SAS openannotation to w3c annotation
    annotation.id = oa_data["@id"];
    annotation.type = "Annotation";
    annotation.motivation = "describing";
    annotation.body = [
        {
            type: "TextualBody",
            value: oa_data.resource[0].chars,
            format: "text/html",
            // "language" : "fr" // TODO!
        },
    ];
    if (oa_data.on.selector["@type"] == "oa:FragmentSelector") {
        annotation.target = {
            selector: {
                type: "FragmentSelector",
                conformsTo: "http://www.w3.org/TR/media-frags/",
                // SAS returns location in xywh=x,y,w,h format; annotorious uses pixel:x,y,w,h
                // it looks like escriptorium locations will need to be scaled!
                value: oa_data.on.selector.value.replace(
                    "xywh=",
                    "xywh=pixel:"
                ),
            },
            source: oa_data.on.full,
        };
    } else if (oa_data.on.selector["@type"].includes("SvgSelector")) {
        annotation.target = {
            selector: {
                type: "SvgSelector",
                value: oa_data.on.selector.value,
            },
            source: oa_data.on.full,
        };
    }
    return annotation;
}

// const AnnotationServerStorage = (client, serverConfig, settings) => {
const AnnotationServerStorage = (client, settings) => {
    let endpointUrl = settings.annotationEndpoint;

    // const collectionName = settings.collectionName || 'annotations';
    // const { annotationTarget } = settings;

    // Load annotations for this image

    // TODO
    fetch(`${endpointUrl}/search?uri=${settings.target}`).then((response) => {
        console.log("search response returned");
        response.json().then((data) => {
            // do something with your data
            console.log(data);
            console.log("annotation resources: ");
            console.log(data[0]);
            // delete them all! workaround for clearing annotations
            // data.forEach(a => deleteAnnotation(a["@id"]));

            let annotations = data.map(toW3CAnnotation);
            console.log(annotations);
            client.setAnnotations(annotations);
            // FIXME: do we need to use sequence mode plugin?
            /// https://github.com/recogito/recogito-client-plugins/tree/main/plugins/annotorious-sequence-mode
        });
    });

    // can annotorious load directly? NOPE
    // client.loadAnnotations(`${endpointUrl}/search?uri=${settings.target}`);

    // db.collection(collectionName).where('target.source', '==', annotationTarget)
    //   .get().then(querySnapshot => {
    //     const annotations = querySnapshot.docs.map(function(doc) {
    //       return doc.data();
    //     });

    //     client.setAnnotations(annotations);
    //   });

    // Lifecycle event handlers
    client.on("createAnnotation", (annotation) => {
        console.log("create");
        console.log(annotation);
        return fetch(`${endpointUrl}/create`, {
            // body: JSON.stringify(SimpleAnnotationServerV2Adapter.createV2Anno(annotation)),
            body: JSON.stringify(annotation), // is annotorious format sufficient?
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            method: "POST",
        })
            .then((response) => {
                console.log("create response returned");
                console.log(response);
            })
            .catch(() => {
                console.log("error...");
            });

        //   db.collection(collectionName)
        //     .add(a).catch(error =>
        //       console.error('Error storing annotation', error, a))
    });

    client.on("updateAnnotation", (annotation, previous) => {
        console.log("update annotation");
        console.log(annotation);
        console.log(previous);
        // POST to /annotation/update
        // The posted annotation should have an @id which exists in the store

        /*findById(previous.id)
          .then(doc => doc.ref.update(annotation))
          .catch(error => console.log('Error updating annotation', error, previous, annotation))*/
    });

    function deleteAnnotation(id) {
        let api_url =
            `${endpointUrl}/destroy?` +
            new URLSearchParams({
                uri: id,
            });
        return fetch(api_url, {
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            method: "DELETE",
        })
            .then((response) => {
                console.log("delete response returned");
                console.log(response);
            })
            .catch(() => {
                console.log("error...");
            });
    }

    client.on("deleteAnnotation", (annotation) => {
        console.log("delete annotation");
        console.log(annotation);
        deleteAnnotation(annotation.id);
    });
};

export default AnnotationServerStorage;
