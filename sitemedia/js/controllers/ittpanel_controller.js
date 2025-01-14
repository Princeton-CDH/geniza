// controllers/ittpanel_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = [
        "emptyLabel",
        "imagePopout",
        "toggle",
        "transcription",
        "translation",
        "rotationSliderToggle",
        "shortLabel",
        "zoomSliderToggle",
    ];

    initialize() {
        // bind "this" so we can access other methods in this controller from within event handler
        this.boundAlertHandler = this.handleSaveAnnotation.bind(this);
        this.boundCancelHandler = this.handleCancelAnnotation.bind(this);
        this.boundResizeHandler = this.handleResizeAlign.bind(this);
    }

    connect() {
        document.addEventListener("tahqiq-alert", this.boundAlertHandler);
        document.addEventListener("tahqiq-cancel", this.boundCancelHandler);
        if (this.isDesktop()) {
            // if transcription + translation both open, align their contents line-by-line
            this.alignLines();
            // align the header of the first image with the headers of the other two columns
            this.alignHeaders();
        }
        // on resize, retrigger alignment
        window.addEventListener("resize", this.boundResizeHandler);
        // a bit hacky; on annotation load, short wait for elements to be created, then align
        // (this is only used in editor environment)
        document.addEventListener("annotations-loaded", () =>
            setTimeout(this.boundResizeHandler, 50)
        );
    }

    disconnect() {
        document.removeEventListener("tahqiq-alert", this.boundAlertHandler);
        document.removeEventListener("tahqiq-cancel", this.boundCancelHandler);
    }

    isDesktop() {
        // Minimum width for desktop devices
        return window.innerWidth >= 900;
    }

    clickToggle() {
        if (this.isDesktop()) {
            // reset alignment; prevents mistakes on lines that change size, clears align if not needed
            this.removeAlignment();
            // when transcription and translation are both opened, align their contents line-by-line
            this.alignLines();
            // realign headers if chanegd
            this.alignHeaders();
        }
    }

    toggleZoomSlider(e) {
        if (
            e.currentTarget.checked &&
            this.rotationSliderToggleTarget.checked
        ) {
            this.rotationSliderToggleTarget.checked = false;
        }
    }

    toggleRotationSlider(e) {
        if (e.currentTarget.checked && this.zoomSliderToggleTarget.checked) {
            this.zoomSliderToggleTarget.checked = false;
        }
    }

    imageAndOtherPanelOpen() {
        // check toggle targets to find out whether both image and either
        // transcription and translation are open
        return (
            this.toggleTargets.find((target) => target.id === "images-on")
                .checked === true &&
            ["transcription-on", "translation-on"].some(
                (id) =>
                    this.toggleTargets.find((target) => target.id === id)
                        .checked === true
            )
        );
    }

    transcriptionAndTranslationOpen() {
        // check toggle targets to find out whether both transcription and translation are open
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

    alignHeaders(forceAlign) {
        // Align the header of the first image with the header row of the transcription and/or
        // translation panels
        if (
            this.imageAndOtherPanelOpen() &&
            this.emptyLabelTarget &&
            this.imagePopoutTargets.length &&
            this.shortLabelTargets.length &&
            (!this.imagePopoutTargets[0].classList.contains("open") ||
                forceAlign)
        ) {
            const emptyHeight = getComputedStyle(this.emptyLabelTarget).height;
            this.imagePopoutTargets[0].style.marginTop = `-${emptyHeight}`;
            this.imagePopoutTargets[0].style.paddingBottom = emptyHeight;
            const shortLabel = this.shortLabelTargets[0];
            const spanHeight = getComputedStyle(shortLabel).height;
            const imgHeader = this.imagePopoutTargets[0].querySelector("h2");
            imgHeader.style.height = spanHeight;
        } else if (this.imagePopoutTargets.length) {
            this.imagePopoutTargets[0].style.removeProperty("margin-top");
            this.imagePopoutTargets[0].style.removeProperty("padding-bottom");
            this.imagePopoutTargets[0]
                .querySelector("h2")
                .style.removeProperty("height");
        }
    }

    popOut(e) {
        // handle img panel alignment when opening and closing the popout container
        if (
            e.currentTarget.classList.contains("active") ||
            e.currentTarget.classList.contains("popout-close-button")
        ) {
            alignHeaders(true);
        } else {
            this.imagePopoutTargets[0].style.removeProperty("margin-top");
            this.imagePopoutTargets[0].style.removeProperty("padding-bottom");
            this.imagePopoutTargets[0]
                .querySelector("h2")
                .style.removeProperty("height");
        }
    }

    alignLines() {
        if (this.transcriptionAndTranslationOpen()) {
            // get the currently selected transcription and translation
            const selectedTranscriptionInput = document.querySelector(
                'input:checked[type="radio"][name="transcription"]'
            );
            let transcriptionChunks = [];
            if (selectedTranscriptionInput) {
                const className =
                    selectedTranscriptionInput.dataset.transcription;
                transcriptionChunks = document.querySelectorAll(
                    `.${className}`
                );
            } else {
                // allow alignment in transcription edit mode (i.e. no selectedTranscriptionInput)
                transcriptionChunks = document.querySelectorAll(
                    ".annotate.transcription"
                );
            }
            const selectedTranslationInput = document.querySelector(
                `input:checked[type="radio"][name="translation"]`
            );
            let translationChunks = [];
            if (selectedTranslationInput) {
                const className = selectedTranslationInput.dataset.translation;
                translationChunks = document.querySelectorAll(`.${className}`);
            } else {
                // allow alignment in translation edit mode (i.e. no selectedTranslationInput)
                translationChunks = document.querySelectorAll(
                    ".annotate.translation"
                );
            }

            // loop through each transcription and translation block (only as many as needed)
            const minTargets = Math.min(
                transcriptionChunks.length,
                translationChunks.length
            );
            for (let i = 0; i < minTargets; i++) {
                // loop through as many OLs in each transcription/translation as needed
                const edOls = transcriptionChunks[i].querySelectorAll("ol");
                const trOls = translationChunks[i].querySelectorAll("ol");
                const minLists = Math.min(edOls.length, trOls.length);
                for (let j = 0; j < minLists; j++) {
                    // first, align tops of lists (using inline styles)
                    const edOl = edOls[j];
                    const trOl = trOls[j];
                    const edTop = edOl.getBoundingClientRect().top;
                    // translation is always 1 pixel difference
                    const trTop = trOl.getBoundingClientRect().top - 1;
                    if (edTop < trTop) {
                        edOl.style.paddingTop = `${trTop - edTop}px`;
                        trOl.style.paddingTop = "0px";
                    } else if (trTop < edTop) {
                        trOl.style.paddingTop = `${edTop - trTop}px`;
                        edOl.style.paddingTop = "0px";
                    } else {
                        trOl.style.paddingTop = "0px";
                        edOl.style.paddingTop = "0px";
                    }
                    // then, align each line of transcription to translation
                    const edLines = edOl.querySelectorAll("li");
                    const trLines = trOl.querySelectorAll("li");
                    // only align as many lines as we need to
                    const minLines = Math.min(edLines.length, trLines.length);
                    for (let k = 0; k < minLines; k++) {
                        if (edLines[k] && trLines[k]) {
                            // calculate number of lines based on line height
                            const maxLineCount = Math.max(
                                this.getLineCount(edLines[k]),
                                this.getLineCount(trLines[k])
                            );
                            // set data-lines attribute on each li according to which is longer
                            edLines[k].setAttribute("data-lines", maxLineCount);
                            trLines[k].setAttribute("data-lines", maxLineCount);
                        }
                    }
                }
            }
        }
    }

    removeAlignment() {
        // remove alignment
        // first remove data-lines from each line
        if (this.hasTranscriptionTarget) {
            this.transcriptionTargets.forEach((target) => {
                target.querySelectorAll("li").forEach((li) => {
                    if (li) li.removeAttribute("data-lines");
                });
            });
        }
        if (this.hasTranslationTarget) {
            this.translationTargets.forEach((target) => {
                target.querySelectorAll("li").forEach((li) => {
                    if (li) li.removeAttribute("data-lines");
                });
            });
        }
        // then remove padding-top alignment of the two lists
        if (this.hasTranscriptionTarget) {
            this.transcriptionTargets.forEach((target) => {
                const edOL = target.querySelector("ol");
                if (edOL) edOL.removeAttribute("style");
            });
        }
        if (this.hasTranslationTarget) {
            this.translationTargets.forEach((target) => {
                const trOL = target.querySelector("ol");
                if (trOL) trOL.removeAttribute("style");
            });
        }
    }

    handleResizeAlign() {
        // on resize, remove alignment and realign using new heights
        if (this.isDesktop()) {
            this.removeAlignment();
            this.alignLines();
            this.alignHeaders();
        }
    }

    handleSaveAnnotation(e) {
        // on save, re-align transcription and translation lines
        if (this.isDesktop()) {
            const { message } = e.detail;
            if (message.includes("saved")) {
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
