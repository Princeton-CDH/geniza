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

            // allow "pop out" image during editing
            const popOutButton = this.imageContainerTarget.querySelector(
                "button.popout-button"
            );
            const closeButton = this.imageContainerTarget.querySelector(
                "button.popout-close-button"
            );
            const popOutContainer =
                this.imageContainerTarget.querySelector(".popout-container");
            popOutButton.addEventListener("click", (e) => {
                // use toggle to allow opening and closing with the pin icon
                popOutContainer.classList.toggle("open");
                closeButton.classList.toggle("visible");
                popOutButton.classList.toggle("active");
            });
            closeButton.addEventListener("click", (e) => {
                popOutContainer.classList.remove("open");
                closeButton.classList.remove("visible");
                popOutButton.classList.remove("active");
            });

            // initialize transcription editor
            // get sibling outside of controller scope:
            // - next sibling for transcription
            // - sibling after next for translation
            const sibling = config.secondary_motivation.includes("transcribing")
                ? this.imageContainerTarget.nextElementSibling
                : this.imageContainerTarget.nextElementSibling
                      .nextElementSibling;
            const annotationContainer = sibling.querySelector(".annotate");

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
        const anno = Annotorious(viewer, { disableDeleteKey: true });

        // initialize toolbar tools
        const rectangleTool = this.element.querySelector(".rect-tool input");
        rectangleTool.addEventListener("change", (e) => {
            if (e.target.checked) {
                anno.setDrawingTool("rect");
                polygonTool.checked = false;
                polygonTool.parentElement.classList.remove("active-tool");
                rectangleTool.parentElement.classList.add("active-tool");
            }
        });
        const polygonTool = this.element.querySelector(".polygon-tool input");
        polygonTool.addEventListener("change", (e) => {
            if (e.target.checked) {
                anno.setDrawingTool("polygon");
                rectangleTool.checked = false;
                polygonTool.parentElement.classList.add("active-tool");
                rectangleTool.parentElement.classList.remove("active-tool");
            }
        });

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
            config.text_direction,
            config.tiny_api_key
        );
        return viewer;
    }
}
