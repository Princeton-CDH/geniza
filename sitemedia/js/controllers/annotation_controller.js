import {
    Controller,
    getControllerForElementAndIdentifier,
} from "@hotwired/stimulus";
import { useIntersection } from "stimulus-use";
import * as Annotorious from "@recogito/annotorious-openseadragon";
import {
    TranscriptionEditor,
    AnnotationServerStorage,
} from "annotorious-tahqiq";

// required imports for self-hosted tinyMCE
import "tinymce/tinymce";
import "tinymce/icons/default";
import "tinymce/themes/silver";
import "tinymce/plugins/lists";
import contentUiCss from "tinymce/skins/ui/oxide/content.css";
import contentCss from "tinymce/skins/content/default/content.css";
import skinCss from "tinymce/skins/ui/oxide/skin.min.css";
import skinShadowDomCss from "tinymce/skins/ui/oxide/skin.shadowdom.min.css";
import skinContentCss from "tinymce/skins/ui/oxide/content.min.css";

export default class extends Controller {
    static targets = ["image", "imageContainer"];

    connect() {
        // enable intersection behaviors (appear, disappear)
        useIntersection(this);
    }
    async appear() {
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
                await this.element.iiif.activateDeepZoom(settings);
                this.initAnnotorious(settings);
            } else {
                this.imageTarget.addEventListener("load", async () => {
                    await this.element.iiif.activateDeepZoom(settings);
                    this.initAnnotorious(settings);
                });
            }
        }
    }

    setNavigatorVisible(visible) {
        // show or hide the OSD navigator
        const viewer = this.element.iiif.viewer;
        if (viewer?.navigator?.element) {
            viewer.navigator.element.style.display = visible ? "block" : "none";
        }
    }

    initAnnotorious(settings) {
        // initialize annotorious, binding to the osd viewer object
        // on the iiif controlleer

        const viewer = this.element.iiif.viewer;

        // enable annotorious-tahqiq
        const { config, canvasURL, manifestId, annotationContainer } = settings;
        const anno = Annotorious(viewer, { disableDeleteKey: true });

        // Initialize the AnnotationServerStorage plugin
        const annotationServerConfig = {
            annotationEndpoint: config.server_url,
            target: canvasURL,
            manifest: config.manifest_base_url + manifestId,
            csrf_token: config.csrf_token,
            lineMode: config.line_mode,
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
            this.element.querySelector(".tahqiq-toolbar"), // toolbar container fieldset
            config.tiny_api_key,
            config.text_direction,
            config.italic_enabled
        );

        if (window.tinyConfig) {
            // add extra tinyMCE configuration required for self-hosted instance
            window.tinyConfig = {
                ...window.tinyConfig,
                // disable attempts to load tinyMCE css from CDN or server; load as modules insetad
                skin: false,
                content_css: false,
                // use css modules for tinyMCE editor inner content style
                content_style: `${contentUiCss} ${contentCss}
                    ::marker { margin-left: 1em; }
                    li { padding-right: 1em; } ins { color: gray; }`,
                setup: (editor) => {
                    editor.on("init", () => {
                        // place imported CSS modules into <style> element inside shadow root.
                        // (hacky but required to get self-hosted tinyMCE webcomponent to see CSS)
                        const editorNode = editor.targetElm;
                        if (!editorNode.parentNode.querySelector("style")) {
                            const style = document.createElement("style");
                            style.textContent = `${skinCss} ${skinContentCss} ${skinShadowDomCss}`;
                            editorNode.parentNode.insertBefore(
                                style,
                                editorNode.nextSibling
                            );
                        }
                    });
                },
            };
        }

        // add some special handling to hide the OSD navigator while drawing
        anno.on("startSelection", () => this.setNavigatorVisible(false));
        anno.on("createSelection", () => this.setNavigatorVisible(true));
        anno.on("cancelSelected", () => this.setNavigatorVisible(true));

        // use a placeholder and show error if opening a tilesource fails
        viewer.addHandler("open-failed", ({ eventSource, message, source }) => {
            storagePlugin.alert(`${message}: ${source}`, "error");
            eventSource.open({ type: "image", url: config.placeholder_img });
        });

        return viewer;
    }
}
