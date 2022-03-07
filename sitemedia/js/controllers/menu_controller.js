// src/controllers/menu.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    // Adapted from W3C web accessibility tutorials:
    // https://www.w3.org/WAI/tutorials/menus/flyout/#flyoutnavkbfixed
    clickSubmenu(e) {
        let link = e.currentTarget;
        if (link.parentNode.classList.contains("open")) {
            link.setAttribute("aria-expanded", "false");
            link.parentNode.classList.remove("open");
        } else {
            link.setAttribute("aria-expanded", "true");
            link.parentNode.classList.add("open");
        }
    }
    openSubmenu(e) {
        const link = e.currentTarget;
        if (link.getAttribute("aria-expanded") === "false") {
            link.setAttribute("aria-expanded", "true");
        }
    }
    closeSubmenu(e) {
        const link = e.currentTarget;
        if (link.getAttribute("aria-expanded") === "true") {
            link.setAttribute("aria-expanded", "false");
        }
    }
}
