import OpenSeadragon from "openseadragon";

let target = document.getElementById("iiif-images");
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
