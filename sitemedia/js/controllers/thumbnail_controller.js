// controllers/thumbnail_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    connect() {
        // attach onerror event listener to every img element here
        this.element.querySelectorAll("img").forEach((img) => {
            img.addEventListener("error", this.handleError);
        });
    }
    async handleError(evt) {
        // if the image fails to load, try to manually create a square crop, in
        // case this is IIIF v2.0 which doesn't support /square/ (e.g. JRL)
        const iiifInfo = evt.target.src.replace(
            /\/square\/60,60\/0\/default\.jpg$/,
            "/info.json"
        );
        try {
            // get width and height from IIIF info.json
            const info = await fetch(iiifInfo);
            const { width, height } = await info.json();
            // manually create a centered, square crop of the image
            const squareEdge = Math.min(width, height);
            const xOffset = Math.floor((width - squareEdge) / 2);
            const yOffset = Math.floor((height - squareEdge) / 2);
            // update the img src with the new IIIF params for that crop
            const newParams = `${xOffset},${yOffset},${squareEdge},${squareEdge}/60,60`;
            evt.target.src = evt.target.src.replace(/square\/60,60/, newParams);
        } catch (err) {
            // if anything fails, image is probably just broken or service is down
            console.error(err);
        }
    }
}
