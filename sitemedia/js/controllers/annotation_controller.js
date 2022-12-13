import { Controller } from "@hotwired/stimulus";
import { useIntersection } from "stimulus-use";
import * as Annotorious from "@recogito/annotorious-openseadragon";
import {
    TranscriptionEditor,
    AnnotationServerStorage,
} from "annotorious-tahqiq";

export default class extends Controller {
    static targets = ["image", "imageContainer"];

    connect() {
        // enable intersection behaviors (appear, disappear)
        useIntersection(this);
    }
    appear() {
        // enable deep zoom, annotorious-tahqiq on first appearance
        // (appear may fire subsequently, but nothing should happen then)
        if (
            !this.imageContainerTarget.querySelector(".openseadragon-container")
        ) {
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
                this.element.iiif.activateDeepZoom(settings);
                this.initAnnotorious(settings);
            } else {
                this.imageTarget.addEventListener("load", () => {
                    this.element.iiif.activateDeepZoom(settings);
                    this.initAnnotorious(settings);
                });
            }
        }
    }
    initAnnotorious(settings) {
        // initialize annotorious, binding to the osd viewer object
        // on the iiif controlleer

        const viewer = this.element.iiif.viewer;

        // enable annotorious-tahqiq
        const { config, canvasURL, manifestId, annotationContainer } = settings;
        const anno = Annotorious(viewer, { handleRadius: 10 });

        // Initialize the AnnotationServerStorage plugin
        const annotationServerConfig = {
            annotationEndpoint: config.server_url,
            target: canvasURL,
            manifest: config.manifest_base_url + manifestId,
            csrf_token: config.csrf_token,
        };
        if (config.source_uri) {
            annotationServerConfig["sourceUri"] = config.source_uri;
        }
        if (config.secondary_motivation) {
            annotationServerConfig["secondaryMotivation"] =
                config.secondary_motivation;
        }
        const storagePlugin = new AnnotationServerStorage(
            anno,
            annotationServerConfig
        );
        // Initialize the TranscriptionEditor plugin
        new TranscriptionEditor(
            anno,
            storagePlugin,
            annotationContainer,
            config.tiny_api_key
        );
        return viewer;
    }
}
