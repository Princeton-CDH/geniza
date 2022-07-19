import * as Annotorious from "@recogito/annotorious-openseadragon";
import {
    TranscriptionEditor,
    AnnotationServerStorage,
} from "annotorious-tahqiq";

import IIIFControler from "./iiif_controller";

export default class extends IIIFControler {
    static targets = [
        "imageContainer",
        "image",
        "zoomSlider",
        "zoomSliderLabel",
        "zoomToggle",
    ];

    connect() {
        // enable deep zoom, annotorious-tahqiq on load

        // load configuration variables from django settings; must use DOM query due to json_script
        const config = JSON.parse(
            document.getElementById("annotation-config").textContent
        );

        // TODO: Better way of determining if we're on mobile?
        const isMobile = window.innerWidth <= 900;

        // initialize transcription editor
        // get sibling outside of controller scope
        const annotationContainer =
            this.imageContainerTarget.nextElementSibling.querySelector(
                ".annotate"
            );

        // grab iiif URL and manifest for tahqiq
        const canvasURL = this.imageContainerTarget.dataset.canvasUrl;
        const manifestId = annotationContainer.dataset.manifest;
        const settings = {
            isMobile,
            config,
            canvasURL,
            manifestId,
            annotationContainer,
        };

        // wait for each image to load fully before enabling OSD so we know its full height
        if (this.imageTarget.complete) {
            this.activateDeepZoom(settings);
        } else {
            this.imageTarget.addEventListener("load", () => {
                this.activateDeepZoom(settings);
            });
        }
    }
    addOpenSeaDragon(settings) {
        const viewer = super.addOpenSeaDragon(settings);
        // enable annotorious-tahqiq
        const { config, canvasURL, manifestId, annotationContainer } = settings;
        const anno = Annotorious(viewer);

        // Initialize the AnnotationServerStorage plugin
        const annotationServerConfig = {
            annotationEndpoint: config.server_url,
            target: canvasURL,
            manifest: config.manifest_base_url + manifestId,
        };
        const storagePlugin = new AnnotationServerStorage(
            anno,
            annotationServerConfig
        );
        // Initialize the TranscriptionEditor plugin
        new TranscriptionEditor(anno, storagePlugin, annotationContainer);
        return viewer;
    }
    handleZoomSliderInput(viewer, minZoom) {
        return (evt) => {
            // Handle changes in the zoom slider
            let zoom = parseFloat(evt.currentTarget.value);
            if (zoom <= minZoom) {
                // prevent zoom from going below minZoom
                zoom = minZoom;
                viewer.viewport.zoomTo(1.0);
                evt.currentTarget.value = minZoom;
            } else {
                // Zoom to the chosen percentage
                viewer.viewport.zoomTo(zoom);
            }
            this.updateZoomUI(zoom, false);
        };
    }
}
