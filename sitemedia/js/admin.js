// Admin Document change form helpers:
// - enable dragging and dropping images within a Document to set the order
// - enable clicking images for an associated TextBlock to set which images are part of the
//   document and which are not
// - enable rotating images within a Document
// - latitude and longitude validation for Places
// - map for places

import maplibregl, { ScaleControl } from "maplibre-gl";

window.addEventListener("DOMContentLoaded", () => {
    // append image rotation/selection controls to each image in the image order
    // field thumbnail display
    appendImageControls();

    // loop through the image order field thumbnail display and attach the drag
    // and drop and rotation behaviors to each image
    attachOverrideEventListeners();

    // loop through the textblock_set tabular inline (uses one row per TextBlock)
    // and attach the click toggle event listener to each image
    const textblockRows = document.querySelectorAll(
        "#textblock_set-group tr.has_original"
    );
    textblockRows.forEach((row) => {
        const thumbnails = row.querySelectorAll(
            "td.field-thumbnail div.admin-thumbnail"
        );
        const selectedImagesField = row.querySelector(
            "td.field-selected_images input[name$='selected_images']"
        );
        thumbnails.forEach((thumbnailDiv, i) => {
            thumbnailDiv.addEventListener(
                "click",
                toggleImageSelected(i.toString(), selectedImagesField)
            );
        });
    });

    // for Footnote doc relations, add event listeners to prevent checking both
    // Digital Edition + Edition checkboxes
    let existingDocRelations = document.querySelectorAll(
        // ^='footnote' captures both Document and Source footnote inlines
        "div[id^='footnote'] td.field-doc_relation > div"
    );
    if (!existingDocRelations.length) {
        // this means we're on the actual Footnote change form and not inline
        existingDocRelations = document.querySelectorAll("div#id_doc_relation");
    }
    existingDocRelations.forEach((inputList) => {
        // add toggle disabled on click
        addDocRelationToggle(inputList);
        // disable any existing relations that should already be disabled
        inputList
            .querySelectorAll("input[type='checkbox']:checked")
            .forEach((cb) => {
                toggleDisabled(inputList, cb);
            });
    });

    // latitude and longitude validation, and map, for Places
    const latField = document.querySelector("input#id_latitude");
    const lonField = document.querySelector("input#id_longitude");
    if (latField && lonField) {
        // center fustat by default
        let lonlat = [31.231, 30.0057];

        // if present, round initial values to 4 decimal places to prevent "step" bug
        if (
            lonField.value &&
            parseFloat(lonField.value) <= 180 &&
            parseFloat(lonField.value) >= -180
        ) {
            lonlat[0] = parseFloat(lonField.value);
            lonField.setAttribute("value", lonlat[0].toFixed(4));
        }
        if (
            latField.value &&
            parseFloat(latField.value) <= 90 &&
            parseFloat(latField.value) >= -90
        ) {
            lonlat[1] = parseFloat(latField.value);
            latField.setAttribute("value", lonlat[1].toFixed(4));
        }

        // add map if we have an access token
        const accessToken = JSON.parse(
            document.getElementById("maptiler-token").textContent
        );
        let marker = null;
        let map = null;
        if (accessToken) {
            const latRow = document.querySelector(".field-latitude");
            const mapContainer = document.createElement("div");
            mapContainer.setAttribute("id", "map");
            mapContainer.style.width = "600px";
            mapContainer.style.height = "400px";
            latRow.parentNode.insertBefore(mapContainer, latRow);
            // add the rtl text plugin to fix arabic text issues
            maplibregl.setRTLTextPlugin(
                "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.2.3/mapbox-gl-rtl-text.min.js",
                true // Lazy load the plugin
            );
            map = new maplibregl.Map({
                container: "map",
                style: `https://api.maptiler.com/maps/5f93d3e5-e339-45bf-86fb-bf7f98a22936/style.json?key=${accessToken}`,
                center: lonlat,
                zoom: 9,
            });

            // add scale controls
            const scaleImperial = new ScaleControl({ unit: "imperial" });
            map.addControl(scaleImperial);
            const scaleMetric = new ScaleControl({ unit: "metric" });
            map.addControl(scaleMetric);

            marker = new maplibregl.Marker({
                draggable: true,
            })
                .setLngLat(lonlat)
                .addTo(map);

            // add event listener to map marker
            marker.on("dragend", () =>
                onDragMapMarker(marker, lonField, latField)
            );
        }
        // attach input event listeners (validate and move marker)
        latField.addEventListener("input", (e) =>
            onLatLonInput(e, marker, map)
        );
        lonField.addEventListener("input", (e) =>
            onLatLonInput(e, marker, map)
        );

        // attach form submit event listener
        const form = document.querySelector("form");
        form.addEventListener("submit", (e) => {
            if (!latField.value || !lonField.value) {
                if (
                    !confirm(
                        "Are you sure you want to save without adding coordinates?"
                    )
                ) {
                    e.preventDefault();
                }
            }
        });
    }
});

function onLatLonInput(evt, marker, map) {
    // show message if invalid
    const isValid = evt.target.reportValidity();
    const asFloat = parseFloat(evt.target.value);
    if (!isValid) {
        if (asFloat) {
            // might be invalid until coerced to float with 4 decimal places
            evt.target.value = parseFloat(asFloat.toFixed(4));
            // remove errors class in that case
            evt.target.parentNode.parentNode.classList.remove("errors");
        } else {
            // add errors class to show red border if invalid
            evt.target.parentNode.parentNode.classList.add("errors");
        }
    } else {
        evt.target.parentNode.parentNode.classList.remove("errors");
    }
    // move marker to new coordinates
    if (map && marker && asFloat) {
        const lngLat = marker.getLngLat();
        try {
            if (evt.target.id.includes("longitude")) {
                marker.setLngLat([asFloat, lngLat.lat]);
                map.jumpTo({ center: [asFloat, lngLat.lat] });
            } else {
                marker.setLngLat([lngLat.lng, asFloat]);
                map.jumpTo({ center: [lngLat.lng, asFloat] });
            }
        } catch (e) {
            // if it's out of bounds, our form validation will catch it anyway
            console.error(e);
        }
    }
}

function onDragMapMarker(marker, lonInput, latInput) {
    // if you drag the marker, set the input values to the marker's coordinates
    const lngLat = marker.getLngLat();
    lonInput.value = lngLat.lng.toFixed(4);
    latInput.value = lngLat.lat.toFixed(4);
}

function addDocRelationToggle(inputList) {
    // add click event listener to the list of checkboxes
    inputList.addEventListener("click", (e) => {
        toggleDisabled(inputList, e.target);
    });
}

function toggleDisabled(inputList, input) {
    // if this is a Digital Edition or Digital Translation checkbox, toggle everything
    // else enabled/disabled, based on whether this one is checked
    const digitalRelations = ["X", "Y"];
    const printRelations = ["E", "T", "D"];
    if (digitalRelations.includes(input.value)) {
        const toToggle = inputList.querySelectorAll(
            `input[type='checkbox']:not([value='${input.value}'])`
        );
        toToggle.forEach((toggle) => {
            toggle.disabled = input.checked && !input.disabled;
        });
    }
    // otherwise, if we clicked on a print relation, toggle the digital relations enabled/disabled
    else if (input.value) {
        // handle special case where multiple print relations are checked and we uncheck
        // just one; in that case, do nothing.
        if (
            !input.checked &&
            printRelations.some(
                (relation) =>
                    inputList.querySelector(
                        `input[type='checkbox'][value='${relation}']`
                    ).checked
            )
        ) {
            return;
        }
        // otherwise, toggle the digital relation checkboxes appropriately
        digitalRelations.forEach((relation) => {
            const toToggle = inputList.querySelector(
                `input[type='checkbox'][value='${relation}']`
            );
            toToggle.disabled = input.checked && !input.disabled;
        });
    }
}

document.addEventListener("formset:added", (event) => {
    if (
        ["footnotes-footnote-content_type-object_id", "footnote_set"].includes(
            event.detail.formsetName
        )
    ) {
        const inputList = event.target.querySelector(
            "td.field-doc_relation > div"
        );
        addDocRelationToggle(inputList);
    }
});

function attachOverrideEventListeners(fromDragEvent) {
    // attach event listeners to images for reorder/rotate functionality.
    // made reusable so that curried event listener functions can be called
    // again with updated nodes once images are reordered
    const imageOverridesDiv = document.querySelector(
        "div.field-admin_thumbnails div.readonly"
    );
    const imageOverrideThumbs =
        imageOverridesDiv?.querySelectorAll("div.admin-thumbnail") || [];
    imageOverrideThumbs.forEach((thumb) => {
        thumb.draggable = true;
        thumb.addEventListener("dragstart", startDrag);
        thumb.addEventListener("dragend", stopDrag(imageOverrideThumbs));
        thumb.addEventListener("dragover", setDraggedOver(imageOverrideThumbs));
        thumb.addEventListener(
            "drop",
            dropImage(imageOverridesDiv, imageOverrideThumbs)
        );
        const rotateLeftButton = thumb.querySelector("button.rotate-left");
        rotateLeftButton.addEventListener("click", rotate(thumb, -90));
        const rotateRightButton = thumb.querySelector("button.rotate-right");
        rotateRightButton.addEventListener("click", rotate(thumb, 90));
        const selectCheckbox = thumb.querySelector("input[type='checkbox']");
        selectCheckbox.addEventListener("input", () => toggleSelected(thumb));
    });
    if (fromDragEvent) {
        // prevent bug where "selected" class applied after drag end
        stopDrag(imageOverrideThumbs)(new DragEvent("dragend"));
    }
}

function appendImageControls() {
    // append a div with rotate left/right buttons, as well as
    // a checkbox for selection, to each image thumbnail
    const orderImages =
        document.querySelectorAll(
            "div.field-admin_thumbnails div.admin-thumbnail"
        ) || [];
    orderImages.forEach((div, i) => {
        const rotationControls = document.createElement("div");
        rotationControls.classList.add("rotation-controls");
        // rotate left button
        const rotateLeftButton = document.createElement("button");
        rotateLeftButton.classList.add("rotate-left");
        rotateLeftButton.setAttribute("type", "button");
        rotateLeftButton.setAttribute(
            "aria-label",
            "rotate 90 degrees counter-clockwise"
        );
        rotateLeftButton.innerHTML = "&#8634;";
        rotationControls.appendChild(rotateLeftButton);
        // rotate right button
        const rotateRightButton = document.createElement("button");
        rotateRightButton.classList.add("rotate-right");
        rotateRightButton.setAttribute("type", "button");
        rotateRightButton.setAttribute(
            "aria-label",
            "rotate 90 degrees clockwise"
        );
        rotateRightButton.innerHTML = "&#8635;";
        rotationControls.appendChild(rotateRightButton);
        div.appendChild(rotationControls);

        // select control
        const selectCheckbox = document.createElement("input");
        selectCheckbox.type = "checkbox";

        const fragmentImage = document.querySelector(
            `#textblock_set-group div.admin-thumbnail[data-canvas="${div.dataset.canvas}"]`
        );
        // match selected state from fragments inline
        if (fragmentImage.classList.contains("selected")) {
            selectCheckbox.checked = true;
            div.classList.add("selected");
        }
        div.appendChild(selectCheckbox);
    });
}

function getOrInitializeOverrides() {
    const field = document.querySelector("input[name='image_overrides']");
    let overrides = {};
    // parse json from field value
    if (field.value) {
        overrides = JSON.parse(field.value);
    }
    const images = document.querySelectorAll(
        "div.field-admin_thumbnails div.admin-thumbnail"
    );
    images.forEach((image, idx) => {
        const canvasUri = image.dataset["canvas"];
        if (Object.hasOwn(overrides, canvasUri)) {
            // if there is an override for this canvas, set any needed defaults
            // default rotation is 0deg
            if (!Object.hasOwn(overrides[canvasUri], "rotation"))
                overrides[canvasUri].rotation = 0;
            // default order is current order
            if (!Object.hasOwn(overrides[canvasUri], "order"))
                overrides[canvasUri].order = idx;
        } else {
            // if there is no override for this canvas, set all defaults
            overrides[canvasUri] = { rotation: 0, order: idx };
        }
    });
    return overrides;
}

function normalize360(degrees) {
    // normalize any degrees value to be within the range 0–360
    while (degrees >= 360) {
        degrees = degrees - 360;
    }
    while (degrees < 0) {
        degrees = degrees + 360;
    }
    return degrees;
}

function toggleSelected(node) {
    // match override section image with textblock fragments image
    const fragmentImage = document.querySelector(
        `#textblock_set-group div.admin-thumbnail[data-canvas="${node.dataset.canvas}"]`
    );
    if (fragmentImage) {
        // send a click event down to the image in textblock fragments, so that
        // toggleImageSelected gets called on it with the appropriate event target
        fragmentImage.click();
        // toggle this image's select class
        node.classList.toggle("selected");
    }
}

function rotate(node, degrees) {
    // rotate an image, a child of `node`, at index `idx`, `degrees` degrees
    return function () {
        const imageOverridesField = document.querySelector(
            "input[name='image_overrides']"
        );
        const canvasUri = node.dataset["canvas"];
        const overrides = getOrInitializeOverrides();
        const oldRotation = parseInt(overrides[canvasUri]["rotation"]);
        let newRotation = normalize360(oldRotation + degrees);

        // get the original rotation from the image source URI
        const img = node.querySelector("img");
        const src = img.getAttribute("src");
        const uriMatches = src.match(/\/\d+\//g);
        const originalRotation = parseInt(
            uriMatches[uriMatches.length - 1].replace(/\//g, "")
        );
        // set the new rotation (taking into consideration the original from URI) as a class
        node.className = node.classList.contains("selected") ? "selected" : "";
        const classList = [
            "admin-thumbnail",
            `rotate-${normalize360(newRotation - originalRotation)}`,
        ];
        node.classList.add(...classList);

        // adjust the width and height of the container to accommodate the rotated image,
        // accounting for controls
        const rect = img.getBoundingClientRect();
        const controlRect = node
            .querySelector(".rotation-controls")
            .getBoundingClientRect();
        const checkboxRect = node
            .querySelector("input[type='checkbox']")
            .getBoundingClientRect();

        node.style.minWidth = `${rect.width}px`;
        node.style.minHeight = `${
            rect.height + controlRect.height + checkboxRect.height
        }px`;

        // finally, update the rotations on the hidden rotation overrides field
        overrides[canvasUri]["rotation"] = newRotation;
        imageOverridesField.setAttribute("value", JSON.stringify(overrides));
    };
}

function startDrag(evt) {
    // on drag start, set the drag data to the dragged item's canvas
    evt.dataTransfer.setData("text", evt.currentTarget.dataset["canvas"]);
}

function stopDrag(thumbnails) {
    // on drag end, ensure no images have "selected" class applied
    return function (evt) {
        evt.preventDefault();
        thumbnails.forEach((thumbnailDiv) => {
            thumbnailDiv.classList.remove("dragtarget");
        });
    };
}

function setDraggedOver(thumbnails) {
    // when an image is dragged over, give it "dragtarget" style (and remove that
    // style from all other images)
    return function (evt) {
        evt.preventDefault();
        const dropTarget = evt.currentTarget;
        dropTarget.classList.add("dragtarget");
        thumbnails.forEach((thumbnailDiv) => {
            if (
                thumbnailDiv.dataset["canvas"] !== dropTarget.dataset["canvas"]
            ) {
                thumbnailDiv.classList.remove("dragtarget");
            }
        });
    };
}

function dropImage(div, thumbnails) {
    // handle image drop on another image: reorder within display field,
    // update hidden image_overrides field with new order of canvases
    return function (evt) {
        evt.preventDefault();

        // use Array instead of NodeList for access to Array prototype functions
        const thumbArray = Array.from(thumbnails).map((thumbnailDiv) => ({
            thumbnailDiv,
            // keep track of selection state
            selected: thumbnailDiv.classList.contains("selected"),
        }));

        // get or initialize rotation override array
        const imageOverridesField = document.querySelector(
            "input[name='image_overrides']"
        );
        let overrides = getOrInitializeOverrides();

        // locate the dragged and dropped canvases in the list
        const draggedCanvas = evt.dataTransfer.getData("text");
        const dragged = thumbArray.find(
            ({ thumbnailDiv }) =>
                thumbnailDiv.dataset["canvas"] === draggedCanvas
        );
        const draggedIndex = thumbArray.indexOf(dragged);
        const dropped = thumbArray.find(
            ({ thumbnailDiv }) => thumbnailDiv === evt.currentTarget
        );
        const droppedIndex = thumbArray.indexOf(dropped);

        // move the dragged image to the correct index
        thumbArray.splice(draggedIndex, 1);
        thumbArray.splice(droppedIndex, 0, dragged);

        // clear out the div, then append each image to it in the new order
        div.innerHTML = "";
        thumbArray.forEach(({ thumbnailDiv, selected }, i) => {
            // add a space before every image except first
            if (i !== 0) {
                div.innerHTML += " ";
            }

            // clone to remove existing event listeners
            const clone = thumbnailDiv.cloneNode(true);
            if (selected) {
                // re-check checkbox as cloning removes this
                clone
                    .querySelector("input[type='checkbox']")
                    .setAttribute("checked", true);
            } else {
                clone
                    .querySelector("input[type='checkbox']")
                    .removeAttribute("checked");
            }
            div.appendChild(clone);

            // update order in overrides
            const canvasUri = thumbnailDiv.dataset["canvas"];
            overrides[canvasUri]["order"] = i;
        });
        // reattach event listeners in order to pass reordered div to curried functions
        // (if we do not do this, the div with the original order is still in evt listeners)
        attachOverrideEventListeners(true);

        // update the hidden image_overrides field's value
        imageOverridesField.setAttribute("value", JSON.stringify(overrides));
    };
}

function toggleImageSelected(image, selectedImagesField) {
    // toggle if this image is selected by adding/removing the "selected" class
    // and adding/removing its index to/from the hidden selected_images form field
    return function (evt) {
        // if this originated from checking a box in the image/rotation overrides
        // section, isTrusted is false
        const fromOverrides = !evt.isTrusted;
        const overrides = document.querySelector(
            "div.field-admin_thumbnails div.readonly"
        );
        const overrideThumb = overrides.querySelector(
            `[data-canvas="${evt.currentTarget.dataset.canvas}"]`
        );
        // if this did not originate from overrides section, make sure overrides
        // section state is synchronized
        if (!fromOverrides) {
            overrideThumb.classList.toggle("selected");
            const checkbox = overrideThumb.querySelector(
                "input[type='checkbox']"
            );
            checkbox.checked = !checkbox.checked;
        }

        // keep hidden field and classlist in sync with selection
        const selectedImages = selectedImagesField.value
            .split(",")
            .filter((v) => v !== ""); // Needed to ensure empty string isn't in array
        const indexInSelected = selectedImages.indexOf(image);
        if (evt.currentTarget.classList.contains("selected")) {
            // if image already selected, then deselect it
            evt.currentTarget.classList.remove("selected");
            if (indexInSelected !== -1)
                selectedImages.splice(indexInSelected, 1);
        } else {
            // if image not selected yet, then select it
            evt.currentTarget.classList.add("selected");
            if (indexInSelected === -1) selectedImages.push(image);
        }
        selectedImagesField.setAttribute("value", selectedImages.join(","));
    };
}
