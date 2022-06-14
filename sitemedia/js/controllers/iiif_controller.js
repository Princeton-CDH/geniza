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
    toggleDeepZoom(evt) {
        // Switch between image and OSD, depending on which is currently active
        const container = evt.currentTarget.parentNode;
        const OSD = container.querySelector(".openseadragon-container");
        const image = container.querySelector("img.iiif-image");
        if (OSD) {
            this.deactivateDeepZoom(container, image);
        } else {
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
        });
        viewer.addHandler("open", function () {
            // ensure image is positioned in top-left corner of viewer
            const bounds = viewer.viewport.getBounds();
            const newBounds = new OpenSeadragon.Rect(
                0,
                0,
                bounds.width,
                bounds.height
            );
            viewer.viewport.fitBounds(newBounds, true);
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
