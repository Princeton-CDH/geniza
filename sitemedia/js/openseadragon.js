import OpenSeadragon from "openseadragon";

function initImageZoom(event) {
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
        });
    }
}

window.addEventListener("turbo:load", initImageZoom);
