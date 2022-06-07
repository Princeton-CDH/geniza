// controllers/iiif_controller.js

import { Controller } from "@hotwired/stimulus";
import OpenSeadragon from "openseadragon";

export default class extends Controller {
    static targets = ["imageContainer"];

    imageContainerTargetDisconnected(element) {
        // remove OSD on target disconnect (i.e. leaving page)
        this.removeOpenSeaDragon(element);
    }
    toggleDeepZoom(evt) {
        // Switch between image and OSD, depending on which is currently active
        const container = evt.target.parentNode.parentNode;
        const OSD = container.querySelector(".openseadragon-container");
        const image = container.querySelector("img.iiif-image");
        if (OSD) {
            container.removeChild(OSD);
            image.style.display = "block";
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
        OpenSeadragon({
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
    }
}
