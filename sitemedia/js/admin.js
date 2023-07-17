// Admin Document change form helpers:
// - enable dragging and dropping images within a Document to set the order
// - enable clicking images for an associated TextBlock to set which images are part of the
//   document and which are not
// - enable rotating images within a Document

window.addEventListener("DOMContentLoaded", () => {
    // append rotation controls to each image in the image order field thumbnail display
    appendRotationControls();

    // loop through the image order field thumbnail display and attach the drag
    // and drop and rotation behaviors to each image
    attachReorderRotateEventListeners();

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
            "td.original input[name$='selected_images']"
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
        "div[id^='footnote'] td.field-doc_relation ul"
    );
    if (!existingDocRelations.length) {
        // this means we're on the actual Footnote change form and not inline
        existingDocRelations = document.querySelectorAll("ul#id_doc_relation");
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
});

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

(function ($) {
    // Apply event listeners to all new rows added to Footnote
    // formset in Document or Source footnote inlines
    // (need to use jQuery to listen to event here until Django 4 upgrade)
    $(document).on("formset:added", function (_, $row, formsetName) {
        if (
            [
                "footnotes-footnote-content_type-object_id",
                "footnote_set",
            ].includes(formsetName)
        ) {
            const inputList = $row.find("td.field-doc_relation ul").get()[0];
            addDocRelationToggle(inputList);
        }
    });
})(django.jQuery);

function attachReorderRotateEventListeners(fromDragEvent) {
    // attach event listeners to images for reorder/rotate functionality.
    // made reusable so that curried event listener functions can be called
    // again with updated nodes once images are reordered
    const orderImagesField = document.querySelector(
        "input[name='image_order_override']"
    );
    const orderImagesDiv = document.querySelector(
        "div.field-admin_thumbnails div.readonly"
    );
    const orderImages =
        orderImagesDiv?.querySelectorAll("div.admin-thumbnail") || [];
    orderImages.forEach((thumb, i) => {
        thumb.draggable = true;
        thumb.addEventListener("dragstart", startDrag);
        thumb.addEventListener("dragend", stopDrag(orderImages));
        thumb.addEventListener("dragover", setDraggedOver(orderImages));
        thumb.addEventListener(
            "drop",
            dropImage(orderImagesField, orderImagesDiv, orderImages)
        );
        const rotateLeftButton = thumb.querySelector("button.rotate-left");
        rotateLeftButton.addEventListener("click", rotate(thumb, i, -90));
        const rotateRightButton = thumb.querySelector("button.rotate-right");
        rotateRightButton.addEventListener("click", rotate(thumb, i, 90));
    });
    if (fromDragEvent) {
        // prevent bug where "selected" class applied after drag end
        stopDrag(orderImages)(new DragEvent("dragend"));
    }
}

function appendRotationControls() {
    // append a div with rotate left and rotate right buttons to each image thumbnail
    const orderImages =
        document.querySelectorAll(
            "div.field-admin_thumbnails div.admin-thumbnail"
        ) || [];
    orderImages.forEach((div, i) => {
        rotationControls = document.createElement("div");
        rotationControls.classList.add("rotation-controls");
        // rotate left button
        rotateLeftButton = document.createElement("button");
        rotateLeftButton.classList.add("rotate-left");
        rotateLeftButton.setAttribute("type", "button");
        rotateLeftButton.setAttribute(
            "aria-label",
            "rotate 90 degrees counter-clockwise"
        );
        rotateLeftButton.innerHTML = "&#8634;";
        rotationControls.appendChild(rotateLeftButton);
        // rotate right button
        rotateRightButton = document.createElement("button");
        rotateRightButton.classList.add("rotate-right");
        rotateRightButton.setAttribute("type", "button");
        rotateRightButton.setAttribute(
            "aria-label",
            "rotate 90 degrees clockwise"
        );
        rotateRightButton.innerHTML = "&#8635;";
        rotationControls.appendChild(rotateRightButton);
        div.appendChild(rotationControls);
    });
}

function getOrInitializeRotations() {
    // if there is already a rotation override, retrieve its value as an array
    // (padded with any 0s if there are missing entries).
    // otherwise, get an array of 0s of the correct length.
    const field = document.querySelector(
        "input[name='image_rotation_override']"
    );
    const len = (
        document.querySelectorAll(
            "div.field-admin_thumbnails div.admin-thumbnail"
        ) || []
    ).length;
    let rotations = new Array(len).fill(0);
    if (field.value) {
        const storedRotations = field.value.split(",");
        rotations = Object.assign(new Array(len).fill(0), storedRotations);
    }
    return rotations;
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

function rotate(node, idx, degrees) {
    // rotate an image, a child of `node`, at index `idx`, `degrees` degrees
    return function () {
        const rotationField = document.querySelector(
            "input[name='image_rotation_override']"
        );
        const rotations = getOrInitializeRotations(rotationField);
        const oldRotation = parseInt(rotations[idx]);
        let newRotation = normalize360(oldRotation + degrees);

        // get the original rotation from the image source URI
        const src = node.querySelector("img").getAttribute("src");
        const uriMatches = src.match(/\/\d+\//g);
        const originalRotation = parseInt(
            uriMatches[uriMatches.length - 1].replace(/\//g, "")
        );
        // set the new rotation (taking into consideration the original from URI) as a class
        node.classList = ["admin-thumbnail"];
        node.classList.add(
            `rotate-${normalize360(newRotation - originalRotation)}`
        );

        // finally, update the rotations on the hidden rotation overrides field
        rotations[idx] = newRotation;
        rotationField.setAttribute("value", rotations);
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
            thumbnailDiv.classList.remove("selected");
        });
    };
}

function setDraggedOver(thumbnails) {
    // when an image is dragged over, give it "selected" style (and remove that
    // style from all other images)
    return function (evt) {
        evt.preventDefault();
        const dropTarget = evt.currentTarget;
        dropTarget.classList.add("selected");
        thumbnails.forEach((thumbnailDiv) => {
            if (
                thumbnailDiv.dataset["canvas"] !== dropTarget.dataset["canvas"]
            ) {
                thumbnailDiv.classList.remove("selected");
            }
        });
    };
}

function dropImage(field, div, thumbnails) {
    // handle image drop on another image: reorder within display field,
    // update hidden image_order_override field with new order of canvases
    return function (evt) {
        evt.preventDefault();

        // use Array instead of NodeList for access to Array prototype functions
        const thumbArray = Array.from(thumbnails);

        // get or initialize rotation override array
        const rotationField = document.querySelector(
            "input[name='image_rotation_override']"
        );
        let rotations = getOrInitializeRotations(rotationField);

        // locate the dragged and dropped canvases in the list
        const draggedCanvas = evt.dataTransfer.getData("text");
        const dragged = thumbArray.find(
            (thumbnailDiv) => thumbnailDiv.dataset["canvas"] === draggedCanvas
        );
        const draggedIndex = thumbArray.indexOf(dragged);
        const draggedRotation = rotations[draggedIndex];
        const droppedIndex = thumbArray.indexOf(evt.currentTarget);

        // move the dragged image to the correct index (both rotation and img order)
        thumbArray.splice(draggedIndex, 1);
        rotations.splice(draggedIndex, 1);
        thumbArray.splice(droppedIndex, 0, dragged);
        rotations.splice(droppedIndex, 0, draggedRotation);

        // clear out the div, then append each image to it in the new order
        div.innerHTML = "";
        thumbArray.forEach((thumbnailDiv, i) => {
            if (i !== 0) {
                div.innerHTML += " ";
            }
            div.appendChild(thumbnailDiv.cloneNode(true)); // clone to remove existing event listeners
        });
        // reattach event listeners in order to pass reordered div to curried functions
        // (if we do not do this, the div with the original order is still in evt listeners)
        attachReorderRotateEventListeners(true);

        // set the hidden image_order_override field's value to the canvases in order
        field.setAttribute(
            "value",
            thumbArray.map((thumbnailDiv) => thumbnailDiv.dataset["canvas"])
        );

        // set the hidden image_rotation_override field's value to the rotations in order
        rotationField.setAttribute("value", rotations);
    };
}

function toggleImageSelected(image, selectedImagesField) {
    // toggle if this image is selected by adding/removing the "selected" class
    // and adding/removing its index to/from the hidden selected_images form field
    return function (evt) {
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
