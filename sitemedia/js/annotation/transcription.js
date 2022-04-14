import * as Annotorious from "@recogito/annotorious-openseadragon";
//import '@recogito/annotorious-openseadragon/dist/annotorious.min.css';
import Toolbar from "@recogito/annotorious-toolbar";
import AnnotationServerStorage from "./sas_storage.js";

function setupAnnotation() {
    if (window.osd_viewer == undefined) {
        return;
    }

    // Initialize the Annotorious plugin
    const config = {}; // Optional plugin config options
    const anno = Annotorious(window.osd_viewer);

    // TODO: track first run and skip unnecessary steps if already run

    // TODO: use event delegation to bind this once instead of on every load
    document.getElementById("enable-annotation").onclick =
        function enableAnnotation() {
            const annotationContainer = document.querySelector(".annotate");
            const iiifContainer = document.getElementById("iiif-images");
            annotationContainer.style.display = "block";
            iiifContainer.setAttribute("class", ""); // remove no-transcription on image if set
        };

    // Initialize the toolbar plugin
    // Toolbar(anno, document.getElementById('toolbar'));

    // Initialize the AnnotationServerStorage plugin
    var annotationServerConfig = {
        annotationEndpoint: "http://0.0.0.0:8888/annotation",
        // testing escriptorium import
        // target: "https://images.lib.cam.ac.uk/iiif/MS-TS-00010-J-00012-00011-000-00001.jp2/info.json",
        // annotationEndpoint:   "https://annotations-staging.princeton.edu/annotation",
    };
    AnnotationServerStorage(anno, annotationServerConfig);
}

window.onload = (event) => {
    console.log("onload: setup annotation");
    setupAnnotation();
};

document.addEventListener("turbo:load", function () {
    console.log("turbo load: setup annotation");
    setupAnnotation();
});

// anno.loadAnnotations('pgpid2806_altoAnnotations.w3c.json');

//       // headless mode, focus on selection tools only
//       anno.disableEditor = true;

//       anno.on("createSelection", function (selection) {
//         // The user has created a new shape...
//         return true;

//       });

//       anno.on("selectAnnotation", function (annotation) {
//         // The user has selected an existing annotation
//         return true;
//       });
