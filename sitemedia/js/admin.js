// Admin Document change form helper to enable clicking images for an associated TextBlock
// to set which images are part of the document and which are not

window.addEventListener("DOMContentLoaded", () => {
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
});

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
