// custom annotation editor for geniza project

const TranscriptionEditor = (anno, storage) => {
    // disable the default annotorious editor (headless mode)
    anno.disableEditor = true;
    const annotationContainer = document.querySelector(".annotate");

    function createDisplayBlock(annotation) {
        let container = document.createElement("div");
        container.setAttribute("class", "annotation-display-container");
        let textInput = document.createElement("div");

        if (annotation.body != undefined && annotation.body.length > 0) {
            textInput.innerHTML = annotation.body[0].value;
        }
        container.append(textInput);

        // existing annotation
        if (annotation.id != undefined) {
            container.dataset.annotationId = annotation.id;

            // when this display is clicked, highlight the zone and make editable
            textInput.onclick = function () {
                anno.selectAnnotation(annotation.id);
                // make sure no other editors are active
                makeAllReadOnly();
                // selection event not fired in this case, so make editable
                makeEditable(container, annotation);
            };
        }

        return container;
    }

    function makeEditable(container, selection) {
        // make an existing display container editable

        // if it's already editable, don't do anything
        if (container.getAttribute("class") == "annotation-edit-container") {
            return;
        }

        container.setAttribute("class", "annotation-edit-container");
        let textInput = container.querySelector("div");
        textInput.setAttribute("class", "annotation-editor");
        textInput.setAttribute("contenteditable", "true");
        textInput.focus();
        // add save and cancel buttons
        let saveButton = document.createElement("button");
        saveButton.setAttribute("class", "save");
        saveButton.textContent = "Save";
        let cancelButton = document.createElement("button");
        cancelButton.setAttribute("class", "cancel");
        cancelButton.textContent = "Cancel";
        container.append(saveButton);
        container.append(cancelButton);

        saveButton.onclick = async function () {
            // add the content to the annotation
            selection.motivation = "supplementing";
            if (selection.body.length == 0) {
                selection.body.push({
                    type: "TextualBody",
                    purpose: "transcribing",
                    value: textInput.textContent,
                    format: "text/html",
                    // TODO: transcription motivation, language, etc.
                });
            } else {
                // assume text content is first body element
                selection.body[0].value = textInput.textContent;
            }
            // update with annotorious, then save to storage backend
            await anno.updateSelected(selection);
            anno.saveSelected();
            // make the editor inactive
            makeReadOnly(container);
        };
        cancelButton.onclick = function () {
            // cancel the edit

            // clear the selection from the image
            anno.cancelSelected();
            // if annotation is unsaved, restore and make read only
            if (container.dataset.annotationId) {
                makeReadOnly(container, selection);
                // if this was a new annotation, remove the container
            } else {
                container.remove();
            }
        };

        // if this is a saved annotation, add delete button
        if (container.dataset.annotationId) {
            let deleteButton = document.createElement("button");
            deleteButton.setAttribute("class", "delete");
            deleteButton.textContent = "Delete";
            container.append(deleteButton);

            deleteButton.onclick = function () {
                // remove the highlight zone from the image
                anno.removeAnnotation(container.dataset.annotationId);
                // remove the edit/display container
                container.remove();
                // calling removeAnnotation doesn't fire the deleteAnnotation,
                // so we have to trigger the deletion explicitly
                storage.adapter.delete(container.dataset.annotationId);
            };
        }

        return container;
    }

    function makeReadOnly(container, annotation) {
        // convert a container that has been made editable back to display format
        // annotation is optional; used to reset content if necessary
        container.setAttribute("class", "annotation-display-container");
        let textInput = container.querySelector("div");
        textInput.setAttribute("class", "");
        textInput.setAttribute("contenteditable", "false");
        // restore the original content
        if (annotation != undefined && annotation.body != undefined) {
            textInput.innerHTML = annotation.body[0].value;
            // add the annotation again to update the image selection region,
            // in case the user has modified it and wants to cancel
            anno.addAnnotation(annotation);
        }
        // remove buttons (or should we just hide them?)
        container.querySelectorAll("button").forEach((el) => el.remove());

        return container;
    }

    function makeAllReadOnly() {
        // make sure no editor is active
        document
            .querySelectorAll(".annotation-edit-container")
            .forEach(function (container) {
                makeReadOnly(container);
            });
    }

    // method to create an editor block
    // container, editable div, buttons to save/cancel/delete
    function createEditorBlock(selection) {
        // create a new annotation editor block and return
        return makeEditable(createDisplayBlock(selection), selection);
    }

    document.addEventListener("annotations-loaded", function () {
        // custom event triggered by storage plugin

        // remove any existing annotation displays, in case of update
        annotationContainer
            .querySelectorAll(".annotation-display-container")
            .forEach((el) => el.remove());
        // display all current annotations
        anno.getAnnotations().forEach(function (annotation) {
            annotationContainer.append(createDisplayBlock(annotation));
        });
    });

    // when a new selection is made, instantiate an editor
    anno.on("createSelection", async function (selection) {
        annotationContainer.append(createEditorBlock(selection));
    });

    anno.on("selectAnnotation", function (annotation) {
        // The users has selected an existing annotation

        // make sure no other editor is active
        makeAllReadOnly();
        // find the display element by annotation id and swith to edit mode
        let displayContainer = document.querySelector(
            '[data-annotation-id="' + annotation.id + '"]'
        );
        makeEditable(displayContainer, annotation);
    });
};

export default TranscriptionEditor;
