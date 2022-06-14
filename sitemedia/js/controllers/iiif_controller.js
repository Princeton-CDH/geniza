// controllers/iiif_controller.js

import { Controller } from "@hotwired/stimulus";
import OpenSeadragon from "openseadragon";

export default class extends Controller {
    static targets = ["imageContainer"];
    static maxZoomPixelRatio = 2.25;

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
        if (!OSD) {
            this.activateDeepZoom(container, image);
        }
    }
    activateDeepZoom(container, image) {
        // hide image and add OpenSeaDragon to container
        const height = container.getBoundingClientRect()["height"];
        container.style.height = `${height}px`;
        image.style.display = "none";
        this.addOpenSeaDragon(container, [container.dataset.iiifUrl]);
    }
    addOpenSeaDragon(element, tileSources) {
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
            maxZoomPixelRatio: this.maxZoomPixelRatio,
        });
        const zoomSlider = element.querySelector("input[type='range']");
        const zoomSliderLabel = element.querySelector(
            "label[for='zoom-slider']"
        );
        viewer.addHandler("open", () => {
            // ensure image is positioned in top-left corner of viewer
            const bounds = viewer.viewport.getBounds();
            const newBounds = new OpenSeadragon.Rect(
                0,
                0,
                bounds.width,
                bounds.height
            );
            viewer.viewport.fitBounds(newBounds, true);

            // initialize zoom slider
            zoomSlider.setAttribute("min", viewer.viewport.getMinZoom());
            zoomSlider.setAttribute("max", viewer.viewport.getMaxZoom());
            zoomSlider.addEventListener("input", (evt) => {
                const zoom = parseFloat(evt.currentTarget.value);
                viewer.viewport.zoomTo(zoom);
                zoomSliderLabel.textContent = `${(zoom * 100).toFixed(0)}%`;
            });
        });
        viewer.addHandler("zoom", (evt) => {
            const { zoom } = evt;
            zoomSlider.value = parseFloat(zoom);
            zoomSliderLabel.textContent = `${(zoom * 100).toFixed(0)}%`;
        });
    }
    deactivateDeepZoom(container, image) {
        const OSD = container.querySelector(".openseadragon-container");
        if (OSD && image) {
            container.removeChild(OSD);
            image.style.display = "block";
        }
    }
}
