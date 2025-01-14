// controllers/transcriptionController.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = [
        "transcriptionShortLabel",
        "transcriptionFullLabel",
        "translationShortLabel",
        "translationFullLabel",
        "dropdownDetails",
    ];

    dropdownDetailsTargetConnected() {
        // switcher is disabled by default; enable if more than one transcription/translation
        this.dropdownDetailsTargets.forEach((target) => {
            if (target.dataset.count > 1) {
                target.removeAttribute("disabled");
                const { relation } = target.dataset;

                // if multiple transcriptions/translations, adjust offset when panel resizes
                this[`${relation}ResizeObserver`] = new ResizeObserver(() => {
                    this.resizePanel(relation);
                });
                this[`${relation}ResizeObserver`].observe(
                    document.querySelector(`div.${relation}-panel`)
                );
            }
        });
    }

    // Change transcription/translation dropdown: pseudo-<select> element with radio buttons to
    // allow styling dropdown menu options list
    changeDropdown(evt) {
        /*
         * Event listener to handle changes to the visible transcription content, and to
         * mimic <select> menu "header" functionality in a details/summary with radio
         * button inputs.
         */
        const relation = evt.currentTarget.name;
        const className = evt.currentTarget.dataset[relation];
        const chunks = document.querySelectorAll(`.${className}`);
        this.scrollChunksIntoView(chunks);

        // Set subheader to show full label for transcription
        this[`${relation}FullLabelTarget`].innerHTML = chunks[0].dataset.label;

        // Mimic "header" functionality by copying the shortened transcription metadata from option to summary
        this[`${relation}ShortLabelTarget`].innerHTML =
            evt.currentTarget.parentElement.textContent;

        // add escr class when appropriate, so we can add logo
        if (evt.currentTarget.parentElement.classList.contains("escr")) {
            this[`${relation}ShortLabelTarget`].classList.add("escr");
        } else {
            this[`${relation}ShortLabelTarget`].classList.remove("escr");
        }
    }

    keyboardCloseDropdown(e) {
        // exit the list and submit on enter/space
        this.dropdownDetailsTargets.forEach((target) => {
            if (
                target.open &&
                (e.code === "Enter" ||
                    e.code === "Space" ||
                    (!e.shiftKey && e.code === "Tab")) // Tab out of a radio button = exiting the list
            ) {
                target.removeAttribute("open");
            }
        });
    }

    shiftTabCloseDropdown(e) {
        // Shift-tab out of the summary = exiting the list
        this.dropdownDetailsTargets.forEach((target) => {
            if (target.open && e.shiftKey && e.code === "Tab") {
                target.removeAttribute("open");
            }
        });
    }

    clickCloseDropdown(e) {
        // Event listener to close the dropdown <details> element when a click is registered outside
        // of it. This needs to be on the whole document because the click could be from anywhere!
        this.dropdownDetailsTargets.forEach((target) => {
            if (target.open) {
                target.removeAttribute("open");
            }
        });
    }

    scrollChunksIntoView(chunks) {
        // Scroll the selected chunks into view
        chunks.forEach((chunk) => {
            chunk.parentNode.scrollLeft =
                chunk.offsetLeft - chunk.parentNode.offsetLeft;
        });
    }

    resizePanel(relation) {
        // When panel changes width, recalculate offsets to make sure
        // the selected transcription/translation is displaying correctly
        const selectedInput = document.querySelector(
            `input:checked[type="radio"][name="${relation}"]`
        );
        if (selectedInput) {
            const className = selectedInput.dataset[relation];
            const chunks = document.querySelectorAll(`.${className}`);
            this.scrollChunksIntoView(chunks);
        }
    }
}
