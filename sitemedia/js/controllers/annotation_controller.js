import * as Annotorious from "@recogito/annotorious-openseadragon";
import AnnotationServerStorage from "annotorious-sas-storage";
import TranscriptionEditor from "annotorious-tahqiq";

import IIIFControler from "./iiif_controller";

export default class extends IIIFControler {
    static targets = ["imageContainer"];

    connect() {
        // enable deep zoom, annotorious-tahqiq on load

        // load configuration variables from django settings; must use DOM query due to json_script
        const config = JSON.parse(
            document.getElementById("annotation-config").textContent
        );

        // TODO: Better way of determining if we're on mobile?
        const isMobile = window.innerWidth <= 900;

        // initialize transcription editor
        const container = this.imageContainerTarget;
        const transcriptionContainer = container.nextElementSibling;
        const annotationContainer =
            transcriptionContainer.querySelector(".annotate");

        // grab iiif URL and manifest for tahqiq
        const canvasURL = container.dataset.canvasUrl;
        const manifestId = annotationContainer.dataset.manifest;
        const settings = {
            isMobile,
            config,
            canvasURL,
            manifestId,
            annotationContainer,
        };

        const image = container.querySelector("img.iiif-image");
        // wait for each image to load fully before enabling OSD so we know its full height
        if (image.complete) {
            this.activateDeepZoom(container, image, settings);
        } else {
            image.addEventListener("load", () => {
                this.activateDeepZoom(container, image, settings);
            });
        }
    }
    addOpenSeaDragon(element, tileSources, settings) {
        const viewer = super.addOpenSeaDragon(element, tileSources, settings);
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
    handleZoomSliderInput(container, image, label, viewer, minZoom) {
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
            this.updateZoomUI(zoom, false, evt.currentTarget, label);
        };
    }
}
