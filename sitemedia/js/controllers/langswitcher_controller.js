// controllers/langswitcher_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    // store url as value attr so that we can use django url resolution
    static values = { url: String };

    connect() {
        document.addEventListener("turbo:frame-load", this.onFrameLoad);
    }

    disconnect() {
        document.removeEventListener("turbo:frame-load", this.onFrameLoad);
    }

    onFrameLoad = (event) => {
        if (event.target.id === "main") {
            // only refresh when "main" frame changes (i.e. the whole page)
            this.refreshSwitcher();
        }
    };

    async refreshSwitcher() {
        // fetch and replace language switcher HTML asynchronously using current
        // URL, on turbo navigation

        // simulate django request.get_full_path()
        const fullPath = `${window.location.pathname}${window.location.search}`;

        // pass to language-switcher endpoint
        const response = await fetch(
            `${this.urlValue}?current_path=${encodeURIComponent(fullPath)}`
        );
        if (response.ok) {
            this.element.innerHTML = await response.text();
        }
    }
}
