// controllers/text_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    async copy(e) {
        // copy the text of the current target to the clipboard
        // NOTE: disabled until we have design for UI feedback on this interaction
        // await navigator.clipboard.writeText(e.currentTarget.innerText);
    }
}
