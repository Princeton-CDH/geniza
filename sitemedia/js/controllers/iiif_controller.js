// controllers/iiif_controller.js

import { Controller } from "@hotwired/stimulus";
import OpenSeadragon from "openseadragon";

export default class extends Controller {
    static targets = ["imageContainer"];

    imageContainerTargetDisconnected(container) {
        // remove OSD on target disconnect (i.e. leaving page)
        const image = container.querySelector("img.iiif-image");
        this.deactivateDeepZoom(container, image);
    }
    handleDeepZoom(evt) {
        // Enable OSD and/or zoom based on zoom slider level
        const container = evt.currentTarget.parentNode.parentNode;
        const OSD = container.querySelector(".openseadragon-container");
        const image = container.querySelector("img.iiif-image");
        if (!OSD || OSD.style.display === "none") {
            this.activateDeepZoom(container, image);
        }
    }
    activateDeepZoom(container, image) {
        // hide image and add OpenSeaDragon to container
        const height = container.getBoundingClientRect()["height"];
        const OSD = container.querySelector(".openseadragon-container");
        container.style.height = `${height}px`;
        image.style.display = "none";
        if (!OSD) {
            this.addOpenSeaDragon(container, [container.dataset.iiifUrl]);
        } else {
            OSD.style.display = "block";
        }
    }
    deactivateDeepZoom(container, image) {
        // Hide OSD and show image
        const OSD = container.querySelector(".openseadragon-container");
        if (OSD && image) {
            OSD.style.display = "none";
            image.style.display = "block";
        }
    }
    addOpenSeaDragon(element, tileSources) {
        // constants for OSD
        const minZoom = 1.0; // Minimum zoom as a multiple of image size
        const maxZoom = 1.5; // Maximum zoom as a multiple of image size

        // inject OSD into the image container
        let viewer = OpenSeadragon({
            element,
            prefixUrl:
                "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/3.0.0/images/",
            tileSources,
            sequenceMode: false,
            autoHideControls: true,
            showHomeControl: false,
            showZoomControl: false,
            showNavigationControl: false,
            showFullPageControl: false,
            showSequenceControl: false,
            crossOriginPolicy: "Anonymous",
            gestureSettingsTouch: {
                pinchRotate: true,
            },
            minZoomImageRatio: minZoom,
            maxZoomPixelRatio: maxZoom,
        });
        const zoomSlider = element.querySelector("input[type='range']");
        const zoomSliderLabel = element.querySelector(
            "label[for='zoom-slider']"
        );
        const image = element.querySelector("img.iiif-image");
        viewer.addHandler("open", () => {
            // ensure image is positioned in top-left corner of viewer
            this.resetBounds(viewer);

            // initialize zoom slider
            zoomSlider.setAttribute("min", minZoom);
            zoomSlider.setAttribute("max", viewer.viewport.getMaxZoom());
            zoomSlider.addEventListener("input", (evt) => {
                // Handle changes in the zoom slider
                let zoom = parseFloat(evt.currentTarget.value);
                if (zoom <= minZoom) {
                    // When zoomed back out to 100%, deactivate OSD
                    zoom = minZoom;
                    this.deactivateDeepZoom(element, image);
                    this.resetBounds(viewer);
                } else {
                    // Zoom to the chosen percentage
                    viewer.viewport.zoomTo(zoom);
                }
                zoomSliderLabel.textContent = `${(zoom * 100).toFixed(0)}%`;
            });
        });
        viewer.addHandler("zoom", (evt) => {
            // Handle changes in the canvas zoom
            let { zoom } = evt;
            if (zoom <= minZoom) {
                // If zooming to less than 100%, force it to 100%
                zoom = minZoom;
            }
            // Set zoom slider value to the chosen percentage
            zoomSlider.value = parseFloat(zoom);
            zoomSliderLabel.textContent = `${(zoom * 100).toFixed(0)}%`;
        });
    }
    resetBounds(viewer) {
        // Reset OSD viewer to the boundaries of the image, position in top left corner
        const bounds = viewer.viewport.getBounds();
        const newBounds = new OpenSeadragon.Rect(
            0,
            0,
            bounds.width,
            bounds.height
        );
        viewer.viewport.fitBounds(newBounds, true);
    }
}
