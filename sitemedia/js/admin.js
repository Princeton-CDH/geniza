// Admin Document change form helpers:
// - enable dragging and dropping images within a Document to set the order
// - enable clicking images for an associated TextBlock to set which images are part of the
//   document and which are not

window.addEventListener("DOMContentLoaded", () => {
    // loop through the image order field thumbnail display and attach the drag
    // and drop behavior to each image
    attachReorderEventListeners();

    // loop through the textblock_set tabular inline (uses one row per TextBlock)
    // and attach the click toggle event listener to each image
    const textblockRows = document.querySelectorAll(
        "#textblock_set-group tr.has_original"
    );
    textblockRows.forEach((row) => {
        const images = row.querySelectorAll("td.field-thumbnail p img");
        const selectedImagesField = row.querySelector(
            "td.original input[name$='selected_images']"
        );
        images.forEach((img, i) => {
            img.addEventListener(
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
    // if this is an Edition or Digital Edition checkbox, toggle the other one
    // of those two enabled/disabled, based on whether this one is checked
    if (["E", "X"].includes(input.value)) {
        const otherRelation = input.value === "X" ? "E" : "X";
        const toToggle = inputList.querySelector(
            `input[type='checkbox'][value='${otherRelation}']`
        );
        // in case of old data with both checked, don't disable both!
        toToggle.disabled = input.checked && !input.disabled;
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

function attachReorderEventListeners(fromDragEvent) {
    // attach event listeners to images for reorder functionality.
    // made reusable so that curried event listener functions can be called
    // again with updated nodes once images are reordered
    const orderImagesField = document.querySelector(
        "input[name='image_order_override']"
    );
    const orderImagesDiv = document.querySelector(
        "div.field-admin_thumbnails div.readonly"
    );
    const orderImages = orderImagesDiv?.querySelectorAll("img") || [];
    orderImages.forEach((img) => {
        img.draggable = true;
        img.addEventListener("dragstart", startDrag);
        img.addEventListener("dragend", stopDrag(orderImages));
        img.addEventListener("dragover", setDraggedOver(orderImages));
        img.addEventListener(
            "drop",
            dropImage(orderImagesField, orderImagesDiv, orderImages)
        );
    });
    if (fromDragEvent) {
        // prevent bug where "selected" class applied after drag end
        stopDrag(orderImages)(new DragEvent("dragend"));
    }
}

function startDrag(evt) {
    // on drag start, set the drag data to the dragged item's canvas
    evt.dataTransfer.setData("text", evt.target.dataset["canvas"]);
}

function stopDrag(images) {
    // on drag end, ensure no images have "selected" class applied
    return function (evt) {
        evt.preventDefault();
        images.forEach((img) => {
            img.classList.remove("selected");
        });
    };
}

function setDraggedOver(images) {
    // when an image is dragged over, give it "selected" style (and remove that
    // style from all other images)
    return function (evt) {
        evt.preventDefault();
        const dropTarget = evt.target;
        dropTarget.classList.add("selected");
        images.forEach((img) => {
            if (img.dataset["canvas"] !== dropTarget.dataset["canvas"]) {
                img.classList.remove("selected");
            }
        });
    };
}

function dropImage(field, div, images) {
    // handle image drop on another image: reorder within display field,
    // update hidden image_order_override field with new order of canvases
    return function (evt) {
        evt.preventDefault();

        // use Array instead of NodeList for access to Array prototype functions
        const imgArray = Array.from(images);
        // locate the dragged and dropped canvases in the list
        const draggedCanvas = evt.dataTransfer.getData("text");
        const dragged = imgArray.find(
            (img) => img.dataset["canvas"] === draggedCanvas
        );
        const draggedIndex = imgArray.indexOf(dragged);
        const droppedIndex = imgArray.indexOf(evt.target);
        // move the dragged image to the correct index
        imgArray.splice(draggedIndex, 1);
        imgArray.splice(droppedIndex, 0, dragged);
        // clear out the div, then append each image to it in the new order
        div.innerHTML = "";
        imgArray.forEach((img, i) => {
            if (i !== 0) {
                div.innerHTML += " ";
            }
            div.appendChild(img.cloneNode()); // clone to remove existing event listeners
        });
        // reattach event listeners in order to pass reordered div to curried functions
        // (if we do not do this, the div with the original order is still in evt listeners)
        attachReorderEventListeners(true);

        // set the hidden image_order_override field's value to the canvases in order
        field.setAttribute(
            "value",
            imgArray.map((img) => img.dataset["canvas"])
        );
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
