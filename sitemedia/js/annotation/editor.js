// custom annotation editor for geniza project

const TranscriptionEditor = (anno) => {
    // disable the default annotorious editor (headless mode)
    anno.disableEditor = true;
    const annotationContainer = document.querySelector(".annotate");

    function createDisplayBlock(annotation) {
        let container = document.createElement("div");
        container.setAttribute("class", "annotation-display-container");
        let textInput = document.createElement("div");
        if (annotation.body[0].value) {
            textInput.innerHTML = annotation.body[0].value;
        }
        container.append(textInput);

        // existing annotation
        console.log("has anotation id");
        if (annotation.id) {
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
        let textInput = container.childNodes[0];
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
            // TODO: handle update!
            console.log("selection body before updating");
            console.log(selection.body);
            selection.body = [
                {
                    type: "TextualBody",
                    purpose: "transcribing",
                    value: textInput.textContent,
                    format: "text/html",
                    // TODO: transcription motivation, language, etc.
                },
            ];
            // TODO: does this get image zone modifications?
            console.log(selection);
            console.log(anno);
            await anno.updateSelected(selection); // .then(function() {
            anno.saveSelected(); // enable when storage works
            // todo: make the editor inactive
        };
        cancelButton.onclick = function () {
            // cancel the edit

            // clear the selection from the image
            anno.cancelSelected();

            // if annotation is unsaved, restore and make read only
            if (container.dataset.annotationId) {
                console.log("making read only");
                console.log(container);
                makeReadOnly(container, selection);
                // if this was a new annotation, remove the container
            } else {
                container.remove();
            }
        };
    }

    function makeReadOnly(container, annotation) {
        // convert a container that has been made editable back to display format
        container.setAttribute("class", "annotation-display-container");
        let textInput = container.querySelector("div");
        console.log(textInput);
        textInput.setAttribute("class", "");
        textInput.setAttribute("contenteditable", "false");
        // restore the original content
        if (annotation != undefined) {
            textInput.innerHTML = annotation.body[0].value;
            // add the annotation again to update the image selection region,
            // in case the user has modified it and wants to cancel
            anno.addAnnotation(annotation);
        }
        // remove save and cancel buttons (or should we just hide them?)
        container.querySelector(".save").remove();
        container.querySelector(".cancel").remove();
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
    // container, editable div, buttons to save/cancel
    function createEditorBlock(selection) {
        // create a new annotation editor block and return
        return makeEditable(createDisplayBlock(selection), selection);
    }

    document.addEventListener("annotations-loaded", function () {
        // custom event triggered by storage plugin
        anno.getAnnotations().forEach(function (annotation) {
            annotationContainer.append(createDisplayBlock(annotation));
        });
    });

    // when a new selection is made, instantiate an editor
    anno.on("createSelection", async function (selection) {
        console.log("create selection");

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
