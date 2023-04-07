// controllers/ittpanel_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["toggle"];

    clickToggle(evt) {
        // when all three toggles are opened, automatically close one, depending on which you
        // attempted to open
        if (this.toggleTargets.every((target) => target.checked)) {
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
    }
}
