// controllers/iiif_controller.js
import { Controller } from "@hotwired/stimulus";
import OpenSeadragon from "openseadragon";

export default class extends Controller {
    static targets = [
        "imageContainer",
        "imageHeader",
        "osd",
        "rotation",
        "rotationEdit",
        "rotationLabel",
        "image",
        "zoomSlider",
        "zoomSliderLabel",
        "zoomToggle",
    ];
    static values = { editMode: { type: Boolean, default: false } };

    connect() {
        // make iiif controller available at element.iiif
        this.element[this.identifier] = this;

        // allow "enlarge" image during viewing
        const enlargeButton = this.imageContainerTarget.querySelector(
            "button.enlarge-button"
        );

        // will not exist if we are in editor
        if (enlargeButton) {
            enlargeButton.addEventListener("click", (e) => {
                // use toggle to allow opening and closing with the pin icon
                this.imageContainerTarget.classList.toggle("enlarged");
                enlargeButton.classList.toggle("active");
            });
        }
    }

    rotationTargetConnected() {
        // initialize angle rotation input
        if (this.osdTarget.dataset.rotation !== "0") {
            this.updateRotationUI(
                parseInt(this.osdTarget.dataset.rotation),
                false,
                true
            );
        }
    }
    osdTargetDisconnected() {
        // remove OSD on target disconnect (i.e. leaving page)
        this.deactivateDeepZoom();
    }
    handleDeepZoom(evt) {
        // Enable OSD if not enabled
        // OSD needs to use DOM queries since it can't be assigned a target
        const OSD = this.osdTarget.querySelector(".openseadragon-container");
        if (!OSD || this.osdTarget.classList.contains("hidden-img")) {
            const isMobile = evt.currentTarget.id.startsWith("zoom-toggle");
            let rotationAngle;
            if (evt.currentTarget.classList.contains("rotation")) {
                // if activated via rotate, ensure zoom UI appears active
                this.updateZoomUI(1.0, false);
                // initial rotation
                rotationAngle = parseInt(evt.currentTarget.value);
            }
            this.activateDeepZoom({ isMobile, rotationAngle });
        }
    }
    async activateDeepZoom(settings) {
        // scroll to top of controls (if not in editor)
        if (!this.editModeValue) {
            this.imageHeaderTarget.scrollIntoView();
        }
        // hide image and add OpenSeaDragon to container
        let OSD = this.osdTarget.querySelector(".openseadragon-container");
        this.imageTarget.classList.remove("visible");
        this.imageTarget.classList.add("hidden-img");
        if (!OSD) {
            await this.addOpenSeaDragon(settings);
            OSD = this.osdTarget.querySelector(".openseadragon-container");
        }
        // OSD styles have to be set directly on the element instead of adding a class, due to
        // its use of inline styles
        OSD.style.position = "absolute";
        OSD.style.transition = "opacity 300ms ease, visibility 0s ease 0ms";
        OSD.style.visibility = "visible";
        OSD.style.opacity = "1";

        this.imageTarget.classList.remove("visible");
        this.imageTarget.classList.add("hidden-img");
        this.osdTarget.classList.remove("hidden-img");
        this.osdTarget.classList.add("visible");
        this.rotationTarget.classList.add("active");
    }

    deactivateDeepZoom() {
        this.imageTarget.classList.add("visible");
        this.imageTarget.classList.remove("hidden-img");
        this.osdTarget.classList.remove("visible");
        this.osdTarget.classList.add("hidden-img");
        this.rotationTarget.classList.remove("active");
        if (this.osdTarget.dataset.rotation !== "0") {
            this.updateRotationUI(
                parseInt(this.osdTarget.dataset.rotation),
                false,
                true
            );
        }
        const OSD = this.osdTarget.querySelector(".openseadragon-container");
        if (OSD) {
            OSD.style.transition =
                "opacity 300ms ease, visibility 0s ease 300ms";
            OSD.style.visibility = "hidden";
            OSD.style.opacity = "0";
        }
    }

    checkTileSource(url) {
        // use HEAD request to check that a tilesource doesn't 404 or cause other errors
        return new Promise((resolve, reject) => {
            fetch(url, { method: "HEAD" })
                .then((response) => {
                    if (response.ok) {
                        resolve(url);
                    } else {
                        reject();
                    }
                })
                .catch(reject);
        });
    }

    async addOpenSeaDragon(settings) {
        const { isMobile, rotationAngle } = settings;

        // constants for OSD
        const minZoom = 1.0; // Minimum zoom as a multiple of image size
        const maxZoom = 1.5; // Maximum zoom as a multiple of image size
        const url = this.osdTarget.dataset.iiifUrl;
        const osdOptions = {
            element: this.osdTarget,
            prefixUrl:
                "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/3.0.0/images/",
            sequenceMode: false,
            autoHideControls: true,
            showHomeControl: false,
            degrees: parseInt(this.osdTarget.dataset.rotation),
            // Enable touch rotation on tactile devices
            gestureSettingsTouch: {
                pinchRotate: true,
            },
            showZoomControl: false,
            showNavigationControl: false,
            navigatorPosition: "TOP_LEFT",
            navigatorOpacity: 0.5,
            showFullPageControl: false,
            showSequenceControl: false,
            crossOriginPolicy: "Anonymous",
            gestureSettingsTouch: {
                pinchRotate: true,
            },
            minZoomImageRatio: minZoom,
            maxZoomPixelRatio: maxZoom,
        };

        // allow placeholder image (url ending in .png instead of .json; assumes all real
        // images are IIIF)
        let isPlaceholder = url.endsWith(".png");

        // placeholder fallback for broken images in annotation mode, must be done on OSD initialization
        const annotationConfig = document.getElementById("annotation-config");
        const handlePlaceholderFallback = (url) => {
            if (annotationConfig && !isPlaceholder) {
                const config = JSON.parse(annotationConfig.textContent);
                // check for a broken image
                return this.checkTileSource(url).then(
                    // image worked: use url
                    () => ({ tileSource: url, isPlaceholder: false }),
                    // image failed: use placeholder img
                    () => {
                        this.element.classList.add("placeholder");
                        return {
                            tileSource: {
                                type: "image",
                                url: config.placeholder_img,
                            },
                            isPlaceholder: true,
                        };
                    }
                );
            } else {
                // not annotation mode, or this was already a placeholder: just use url
                const tileSource = isPlaceholder
                    ? { type: "image", url: url }
                    : url;
                return Promise.resolve({ tileSource, isPlaceholder });
            }
        };

        return handlePlaceholderFallback(url).then(
            ({ tileSource, isPlaceholder }) => {
                // initialize viewer with resolved tilesource
                const viewer = OpenSeadragon({
                    ...osdOptions,
                    tileSources: [tileSource],
                    // show navigator in top left (unless placeholder)
                    showNavigator: !isPlaceholder,
                });
                viewer.addHandler("open", () => {
                    // zoom to current zoom
                    viewer.viewport.zoomTo(
                        parseFloat(this.zoomSliderTarget.value)
                    );
                    // ensure image is positioned in top-left corner of viewer
                    this.resetBounds(viewer);
                    if (isMobile) {
                        // zoom to 110% if on mobile
                        viewer.viewport.zoomTo(1.1);
                        if (!this.zoomToggleTarget.checked) {
                            this.zoomToggleTarget.checked = true;
                        }
                    }
                    if (this.isValidRotation(rotationAngle)) {
                        viewer.viewport.setRotation(rotationAngle);
                    }
                    // initialize zoom slider
                    this.zoomSliderTarget.setAttribute("min", minZoom);
                    // use toPrecision to ensure no extra pixels on the right of the slider
                    this.zoomSliderTarget.setAttribute(
                        "max",
                        viewer.viewport.getMaxZoom().toPrecision(2)
                    );
                    this.zoomSliderTarget.addEventListener(
                        "input",
                        this.handleZoomSliderInput(viewer, minZoom)
                    );
                    // initialize mobile zoom toggle
                    this.zoomToggleTarget.addEventListener("input", (evt) => {
                        // always first zoom to 100%
                        viewer.viewport.zoomTo(1.0);
                        if (!evt.currentTarget.checked) {
                            // wait to reset bounds until element is hidden
                            setTimeout(() => this.resetBounds(viewer), 300);
                            this.deactivateDeepZoom();
                        } else {
                            // reset bounds immediately and zoom to 110%
                            this.resetBounds(viewer);
                            viewer.viewport.zoomTo(1.1);
                        }
                    });
                    // initialize desktop rotation control
                    this.rotationTarget.addEventListener(
                        "input",
                        this.handleRotationInput(viewer)
                    );
                    this.rotationEditTarget.addEventListener(
                        "input",
                        this.handleRotationEditInput(viewer)
                    );
                    this.rotationTarget.addEventListener(
                        "change",
                        this.handleRotationInput(viewer)
                    );
                });
                viewer.addHandler("zoom", (evt) => {
                    // Handle changes in the canvas zoom
                    let { zoom } = evt;
                    if (zoom <= minZoom) {
                        // If zooming to less than 100%, force it to 100%
                        zoom = minZoom;
                    }
                    // Set zoom slider value to the chosen percentage
                    this.zoomSliderTarget.value = parseFloat(zoom);
                    this.updateZoomUI(zoom, false);
                });

                // keep reference to OSD viewer object on the controller object
                this.viewer = viewer;
                return viewer;
            }
        );
    }
    handleRotationInput(viewer) {
        return (evt) => {
            let angle = parseInt(evt.currentTarget.value);
            viewer.viewport.setRotation(angle);
            this.updateRotationUI(angle, evt);
        };
    }
    handleRotationEditInput(viewer) {
        return (evt) => {
            let angle = parseInt(evt.currentTarget.value);
            if (this.isValidRotation(angle)) {
                viewer.viewport.setRotation(angle);
            }
        };
    }
    handleZoomSliderInput(viewer, minZoom) {
        return (evt) => {
            // Handle changes in the zoom slider
            let zoom = parseFloat(evt.currentTarget.value);
            let deactivating = false;
            if (zoom <= minZoom) {
                // When zoomed back out to 100%, deactivate OSD (if not in editor)
                zoom = minZoom;
                viewer.viewport.zoomTo(1.0);
                if (!this.editModeValue) {
                    this.resetBounds(viewer);
                    this.deactivateDeepZoom();
                    deactivating = true;
                }
                evt.currentTarget.value = minZoom;
            } else {
                // Zoom to the chosen percentage
                viewer.viewport.zoomTo(zoom);
            }
            this.updateZoomUI(zoom, deactivating);
        };
    }
    updateSlider(slider, percent, deactivating) {
        let color = "--link-primary";
        if (deactivating) {
            this.zoomSliderTarget.classList.remove("active-thumb");
            this.rotationTarget.classList.remove("active-thumb");
            color = "--filter-active";
        } else if (!slider.classList.contains("active-thumb")) {
            this.zoomSliderTarget.classList.add("active-thumb");
            this.rotationTarget.classList.add("active-thumb");
        }
        // switch gradient direction for RTL layout
        const dir = document.documentElement.dir == "rtl" ? "left" : "right";
        // use gradient for two-tone slider track background
        slider.style.background = `linear-gradient(to ${dir}, var(${color}) 0%, var(${color}) ${percent}%, var(--zoom-control-bg) ${percent}%, var(--zoom-control-bg) 100%)`;
    }
    updateZoomUI(zoom, deactivating) {
        // update the zoom controls UI with the new value

        // update the zoom percentage label
        this.zoomSliderLabelTarget.textContent = `${(zoom * 100).toFixed(0)}%`;
        // update progress indication in slider track
        const percent =
            ((zoom - 1) / (this.zoomSliderTarget.getAttribute("max") - 1)) *
            100;
        this.updateSlider(this.zoomSliderTarget, percent, deactivating);
        if (deactivating) {
            this.updateRotationUI(
                parseInt(this.osdTarget.dataset.rotation) || 0,
                false,
                true
            );
        }
    }
    isValidRotation(angle) {
        return Number.isInteger(angle) && angle >= 0 && angle <= 360;
    }
    editRotation() {
        const angle = parseInt(this.rotationEditTarget.value, 10);
        if (this.isValidRotation(angle)) {
            this.updateRotationUI(angle, false, false);
        }
    }
    updateRotationUI(angle, autoUpdate, deactivating) {
        // update rotation label
        this.rotationLabelTarget.innerHTML = `${angle}&deg;`;
        this.rotationEditTarget.value = angle;
        if (!autoUpdate) {
            // update input value and pivot angle
            this.rotationTarget.value = angle.toString();
        }
        const percent = (angle / 360) * 100;
        this.updateSlider(this.rotationTarget, percent, deactivating);
    }
    resetBounds(viewer) {
        // Reset OSD viewer to the boundaries of the image, position in top left corner
        // (cannot use viewport.goHome() without hacks, as its bounds cannot be configured)
        const bounds = viewer.viewport.getBounds();
        const newBounds = new OpenSeadragon.Rect(
            0,
            0,
            bounds.width,
            bounds.height
        );
        viewer.viewport.fitBounds(newBounds, true);
        viewer.viewport.setRotation(
            parseInt(this.osdTarget.dataset.rotation),
            true
        );
    }
}
