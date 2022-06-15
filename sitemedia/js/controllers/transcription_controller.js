// controllers/transcriptionController.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["dropdownLabel", "dropdownDetails"];

    // Change transcription dropdown: pseudo-<select> element with radio buttons to allow styling
    // dropdown menu options list

    changeTranscription(evt) {
        /*
         * Event listener to handle changes to the visible transcription content, and to
         * mimic <select> menu "header" functionality in a details/summary with radio
         * button inputs.
         */
        const edition = evt.currentTarget.dataset.edition;
        const chunks = document.querySelectorAll(`#${edition}`);
        chunks.forEach((chunk) => {
            chunk.parentNode.scrollLeft =
                chunk.offsetLeft - chunk.parentNode.offsetLeft;
        });
        this.setDropdownLabel(evt.currentTarget.parentElement.textContent);
    }
    setDropdownLabel(label) {
        this.dropdownLabelTarget.children[0].innerHTML = label;
    }

    keyboardCloseDropdown(e) {
        // exit the list and submit on enter/space
        if (
            this.dropdownDetailsTarget.open &&
            (e.code === "Enter" ||
                e.code === "Space" ||
                (!e.shiftKey && e.code === "Tab")) // Tab out of a radio button = exiting the list
        ) {
            this.dropdownDetailsTarget.removeAttribute("open");
        }
    }

    shiftTabCloseDropdown(e) {
        // Shift-tab out of the summary = exiting the list
        if (this.dropdownDetailsTarget.open && e.shiftKey && e.code === "Tab") {
            this.dropdownDetailsTarget.removeAttribute("open");
        }
    }

    clickCloseDropdown(e) {
        // Event listener to close the dropdown <details> element when a click is registered outside
        // of it. This needs to be on the whole document because the click could be from anywhere!
        if (this.dropdownDetailsTarget.open) {
            this.dropdownDetailsTarget.removeAttribute("open");
        }
    }
}
