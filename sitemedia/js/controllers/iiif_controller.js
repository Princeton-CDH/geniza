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
        if (!OSD || OSD.style.opacity === "0") {
            const isMobile = evt.currentTarget.id.startsWith("zoom-toggle");
            this.activateDeepZoom(container, image, isMobile);
        }
    }
    activateDeepZoom(container, image, isMobile) {
        // hide image and add OpenSeaDragon to container
        const height = container.getBoundingClientRect()["height"];
        let OSD = container.querySelector(".openseadragon-container");
        container.style.height = `${height}px`;
        image.classList.remove("visible");
        image.classList.add("hidden");
        if (!OSD) {
            this.addOpenSeaDragon(
                container,
                [container.dataset.iiifUrl],
                isMobile
            );
            OSD = container.querySelector(".openseadragon-container");
        }
        // OSD styles have to be set directly on the element instead of adding a class, due to
        // its use of inline styles
        OSD.style.position = "absolute";
        OSD.style.transition = "opacity 300ms ease, visibility 0s ease 0ms";
        OSD.style.visibility = "visible";
        OSD.style.opacity = "1";
        // OSD needs top offset due to margin, padding, and header elements
        if (isMobile) {
            OSD.style.top = "122px";
        } else {
            OSD.style.top = "118px";
        }
    }
    deactivateDeepZoom(container, image) {
        // Hide OSD and show image
        const OSD = container.querySelector(".openseadragon-container");
        if (OSD && image) {
            OSD.style.transition =
                "opacity 300ms ease, visibility 0s ease 300ms";
            OSD.style.visibility = "hidden";
            OSD.style.opacity = "0";
            image.classList.add("visible");
            image.classList.remove("hidden");
        }
    }
    addOpenSeaDragon(element, tileSources, isMobile) {
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
            "label[for^='zoom-slider']"
        );
        const zoomToggle = element.querySelector(
            "input[type='checkbox'][id^='zoom-toggle']"
        );
        const image = element.querySelector("img.iiif-image");
        viewer.addHandler("open", () => {
            // ensure image is positioned in top-left corner of viewer
            this.resetBounds(viewer);
            if (isMobile) {
                // zoom to 110% if on mobile
                viewer.viewport.zoomTo(1.1);
            }
            // initialize zoom slider
            zoomSlider.setAttribute("min", minZoom);
            zoomSlider.setAttribute("max", viewer.viewport.getMaxZoom());
            zoomSlider.addEventListener("input", (evt) => {
                // Handle changes in the zoom slider
                let zoom = parseFloat(evt.currentTarget.value);
                if (zoom <= minZoom) {
                    // When zoomed back out to 100%, deactivate OSD
                    zoom = minZoom;
                    this.resetBounds(viewer);
                    this.deactivateDeepZoom(element, image);
                    evt.currentTarget.value = minZoom;
                } else {
                    // Zoom to the chosen percentage
                    viewer.viewport.zoomTo(zoom);
                }
                this.updateZoomUI(zoom, zoomSlider, zoomSliderLabel);
            });
            // initialize mobile zoom toggle
            zoomToggle.addEventListener("input", (evt) => {
                // always first zoom to 100%
                viewer.viewport.zoomTo(1.0);
                if (!evt.currentTarget.checked) {
                    // wait to reset bounds until element is hidden
                    setTimeout(() => this.resetBounds(viewer), 300);
                    this.deactivateDeepZoom(element, image);
                } else {
                    // reset bounds immediately and zoom to 110%
                    this.resetBounds(viewer);
                    viewer.viewport.zoomTo(1.1);
                }
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
            this.updateZoomUI(zoom, zoomSlider, zoomSliderLabel);
        });
        if (isMobile) {
            viewer.addHandler("canvas-release", () => {
                // Handle issue on mobile that causes a scroll trap
                window.scrollTo(zoomToggle.scrollTop);
            });
        }
    }
    updateZoomUI(zoom, slider, label) {
        // update the zoom controls UI with the new value
        // update the zoom percentage label
        label.textContent = `${(zoom * 100).toFixed(0)}%`;
        // update progress indication in slider track
        const percent = (zoom / slider.getAttribute("max")) * 100;
        slider.style.background = `linear-gradient(to right, var(--filter-active) 0%, var(--filter-active) ${percent}%, #9e9e9e ${percent}%, #9e9e9e 100%)`;
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
        viewer.viewport.setRotation(0, true);
    }
    scrollTo0(evt) {
        // Scroll container to top; necessary to prevent scroll issue when OSD is positioned absolutely
        evt.currentTarget.scrollTop = 0;
    }
}
