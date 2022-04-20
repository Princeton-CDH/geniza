import * as Annotorious from "@recogito/annotorious-openseadragon";
//import '@recogito/annotorious-openseadragon/dist/annotorious.min.css';
import Toolbar from "@recogito/annotorious-toolbar";
import AnnotationServerStorage from "./sas_storage.js";
import TranscriptionEditor from "./editor.js";

function setupAnnotation() {
    if (window.osd_viewer == undefined) {
        return;
    }

    // TODO: track first run and skip unnecessary steps if already run
    const annotationContainer = document.querySelector(".annotate");
    const transcriptionContainer = document.querySelector(".transcription");
    const manifestId = annotationContainer.dataset.manifest;
    const iiifContainer = document.getElementById("iiif-images");
    const iiifURLs = JSON.parse(iiifContainer.dataset.iiifUrls);

    // TODO: per turbo docs, use event delegation to bind this once instead of on every load
    document.getElementById("enable-annotation").onclick =
        function enableAnnotation() {
            annotationContainer.style.display = "block";
            iiifContainer.setAttribute("class", ""); // remove no-transcription on image if set
            // hide default transcription display
            transcriptionContainer.style.display = "none";

            initAnnotation();
            // disable the button so it can't be clicked again (for now)
            document
                .getElementById("enable-annotation")
                .setAttribute("disabled", "disabled");
        };

    function initAnnotation() {
        // FIXME: only allow init once!
        const anno = Annotorious(window.osd_viewer);
        // load configuration variables from django settings
        const config = JSON.parse(
            document.getElementById("annotation-config").textContent
        );

        // Initialize the toolbar plugin (will likely add later)
        // Toolbar(anno, document.getElementById('toolbar'));

        // Initialize the AnnotationServerStorage plugin
        let annotationServerConfig = {
            annotationEndpoint: config.server_url,
            target: iiifURLs[0], // target first image for now
            manifest: config.manifest_base_url + manifestId,
        };
        AnnotationServerStorage(anno, annotationServerConfig);

        // Initialize the TranscriptionEditor plugin
        TranscriptionEditor(anno);
    }
}

window.onload = (event) => {
    console.log("onload: setup annotation");
    setupAnnotation();
};

document.addEventListener("turbo:load", function () {
    console.log("turbo load: setup annotation");
    setupAnnotation();
});
