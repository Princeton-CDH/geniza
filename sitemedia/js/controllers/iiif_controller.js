// controllers/iiif_controller.js

import { Controller } from "@hotwired/stimulus";
import OpenSeadragon from "openseadragon";

export default class extends Controller {
    static targets = ["iiifContainer"];

    iiifContainerTargetConnected() {
        // inject OSD into the iiif container
        const viewer = OpenSeadragon({
            id: this.iiifContainerTarget.id,
            prefixUrl:
                "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/3.0.0/images/",
            tileSources: JSON.parse(this.iiifContainerTarget.dataset.iiifUrls),
            sequenceMode: true,
            preserveViewport: true,
            autoHideControls: false,
            showHomeControl: false,
            showRotationControl: true,
            // Enable touch rotation on tactile devices
            gestureSettingsTouch: {
                pinchRotate: true,
            },
            crossOriginPolicy: "Anonymous",
            gestureSettingsTouch: {
                pinchRotate: true,
            },
        });

        // store OSD viewer instance on the browser window for access with annotations
        window.osd_viewer = viewer;
    }

    iiifContainerTargetDisconnected() {
        // ensure OSD is removed on disconnect by removing all child nodes from target
        while (this.iiifContainerTarget.firstChild) {
            this.iiifContainerTarget.removeChild(
                this.iiifContainerTarget.firstChild
            );
        }
        delete window.osd_viewer;
    }
}
