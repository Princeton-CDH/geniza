// controllers/ittpanel_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["toggle", "transcription", "translation"];

    initialize() {
        // bind "this" so we can access other methods in this controller from within event handler
        this.boundAlertHandler = this.handleSaveAnnotation.bind(this);
        this.boundCancelHandler = this.handleCancelAnnotation.bind(this);
    }

    connect() {
        document.addEventListener("tahqiq-alert", this.boundAlertHandler);
        document.addEventListener("tahqiq-cancel", this.boundCancelHandler);
        if (this.isDesktop() && this.transcriptionAndTranslationOpen()) {
            // if transcription + translation both open, align their contents line-by-line
            this.alignLines();
        }
    }

    disconnect() {
        document.removeEventListener("tahqiq-alert", this.boundAlertHandler);
        document.removeEventListener("tahqiq-cancel", this.boundCancelHandler);
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
                // close transcription if you opened images
                case "images-on":
                    this.toggleTargets.find(
                        (target) => target.id === "transcription-on"
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
                // when one of those two toggles is closed, remove data-lines from each line (alignment no longer needed)
                this.transcriptionTarget
                    .querySelectorAll("li")
                    .forEach((li) => {
                        li.removeAttribute("data-lines");
                    });
                this.translationTarget.querySelectorAll("li").forEach((li) => {
                    li.removeAttribute("data-lines");
                });
                // also remove padding-top alignment of the two lists
                this.transcriptionTarget
                    .querySelector("ol")
                    .removeAttribute("style");
                this.translationTarget
                    .querySelector("ol")
                    .removeAttribute("style");
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

    getLineCount(el) {
        // determine the number of lines by dividing element's rendered height
        // by its computed line height from CSS, and applying a floor function
        return Math.floor(
            el.getBoundingClientRect().height /
                parseInt(getComputedStyle(el).getPropertyValue("line-height"))
        );
    }

    alignLines() {
        // first, align tops of lists (using inline styles)
        const edTop = this.transcriptionTarget
            .querySelector("ol")
            .getBoundingClientRect().top;
        const trTop = this.translationTarget
            .querySelector("ol")
            .getBoundingClientRect().top;
        if (edTop < trTop) {
            this.transcriptionTarget.querySelector("ol").style.paddingTop = `${
                trTop - edTop
            }px`;
        } else if (trTop < edTop) {
            this.translationTarget.querySelector("ol").style.paddingTop = `${
                edTop - trTop
            }px`;
        }

        // then, align each line of transcription to translation
        const edLines = this.transcriptionTarget.querySelectorAll("li");
        const trLines = this.translationTarget.querySelectorAll("li");
        // only align as many lines as we need to
        const minLines = Math.min(edLines.length, trLines.length);
        for (let i = 0; i < minLines; i++) {
            if (edLines[i] && trLines[i]) {
                // calculate number of lines based on line height
                const maxLineCount = Math.max(
                    this.getLineCount(edLines[i]),
                    this.getLineCount(trLines[i])
                );
                // set data-lines attribute on each li according to which is longer
                edLines[i].setAttribute("data-lines", maxLineCount);
                trLines[i].setAttribute("data-lines", maxLineCount);
            }
        }
    }

    handleSaveAnnotation(e) {
        // on save, re-align transcription and translation lines
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

    handleCancelAnnotation() {
        // on cancel, re-align transcription and translation lines.
        // odd quirk of the reload: we have to wait 1ms for the queryselector to work.
        if (this.isDesktop() && this.transcriptionAndTranslationOpen()) {
            setTimeout(() => {
                this.alignLines();
            }, 1);
        }
    }
}
