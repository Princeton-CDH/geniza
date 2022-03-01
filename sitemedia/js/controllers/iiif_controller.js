// controllers/iiif_controller.js

import { Controller } from "@hotwired/stimulus";
import OpenSeadragon from "openseadragon";

export default class extends Controller {
    connect() {
        let target = document.getElementById("iiif-images");
        if (target != null) {
            let viewer = OpenSeadragon({
                id: target.id,
                prefixUrl:
                    "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/3.0.0/images/",
                tileSources: JSON.parse(target.dataset.iiifUrls),
                sequenceMode: true,
                preserveViewport: true,
                autoHideControls: false,
                showHomeControl: false,
                showRotationControl: true,
                crossOriginPolicy: "Anonymous",
            });
        }
    }
}
