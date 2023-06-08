// controllers/ittpanel_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["toggle", "transcription", "translation"];

    initialize() {
        // bind "this" so we can access other methods in this controller from within event handler
        this.boundAlertHandler = this.handleSaveAnnotation.bind(this);
    }

    connect() {
        document.addEventListener("tahqiq-alert", this.boundAlertHandler);
    }

    disconnect() {
        document.removeEventListener("tahqiq-alert", this.boundAlertHandler);
    }

    isDesktop() {
        // Minimum width for desktop devices
        return window.innerWidth >= 900;
    }

    clickToggle(evt) {
        // when all three toggles are opened, automatically close one, depending on which you
        // attempted to open
        if (this.toggleTargets.every((target) => target.checked)) {
            // NOTE: Logic for which should close and which should remain open was determined via
            // consultation with researchers. The primary finding was that most often, researchers
            // are not looking directly at an image while editing/working on translations.
            switch (evt.target.id) {
                // close translation if you opened images
                case "images-on":
                    this.toggleTargets.find(
                        (target) => target.id === "translation-on"
                    ).checked = false;
                    break;
                // close images if you opened either of the other two
                case "transcription-on":
                case "translation-on":
                    this.toggleTargets.find(
                        (target) => target.id === "images-on"
                    ).checked = false;
                    break;
            }
        }

        if (this.isDesktop()) {
            if (this.transcriptionAndTranslationOpen()) {
                // when transcription and translation are both opened, align their contents line-by-line
                this.alignLines();
            } else {
                // when one of those two toggles is closed, remove inline styles from lines (alignment no longer needed)
                this.transcriptionTarget
                    .querySelectorAll("li")
                    .forEach((li) => {
                        li.removeAttribute("style");
                    });
                this.translationTarget.querySelectorAll("li").forEach((li) => {
                    li.removeAttribute("style");
                });
            }
        }
    }

    transcriptionAndTranslationOpen() {
        // check toggle targets to find out whether both transcription and translated are open
        return ["transcription-on", "translation-on"].every(
            (id) =>
                this.toggleTargets.find((target) => target.id === id)
                    .checked === true
        );
    }

    alignLines() {
        // align each line of transcription to translation
        const edLines = this.transcriptionTarget.querySelectorAll("li");
        const trLines = this.translationTarget.querySelectorAll("li");
        // only align as many lines as we need to
        const minLines = Math.min(edLines.length, trLines.length);
        for (let i = 0; i < minLines; i++) {
            if (edLines[i] && trLines[i]) {
                // compare top of lines by position in list
                const edLiPos = edLines[i].getBoundingClientRect();
                const trLiPos = trLines[i].getBoundingClientRect();
                // add padding-top to the elements that need it
                if (edLiPos.top < trLiPos.top) {
                    edLines[i].style.paddingTop = `${
                        trLiPos.top - edLiPos.top
                    }px`;
                } else if (edLiPos.top > trLiPos.top) {
                    trLines[i].style.paddingTop = `${
                        edLiPos.top - trLiPos.top
                    }px`;
                }
            }
        }
    }

    handleSaveAnnotation(e) {
        // on save, re-align transcription and translation lines
        // TODO: handle cancel?
        if (this.isDesktop()) {
            const { message } = e.detail;
            if (
                message.includes("saved") &&
                this.transcriptionAndTranslationOpen()
            ) {
                this.alignLines();
            }
        }
    }
}
