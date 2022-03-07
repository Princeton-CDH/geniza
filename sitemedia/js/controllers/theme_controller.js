// src/controllers/theme.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["toggleLabel", "toggleCheckbox"];

    systemDarkMode() {
        // Check system and prior user selection for dark mode
        return (
            window.localStorage.getItem("darkMode") === "true" ||
            (window.localStorage.getItem("darkMode") === null &&
                window.matchMedia &&
                window.matchMedia("(prefers-color-scheme: dark)").matches)
        );
    }

    setMode(mode) {
        // Toggle light/dark mode using classes on body element
        this.element.classList.add(`${mode}-mode`);
        this.element.classList.remove(
            `${mode === "light" ? "dark" : "light"}-mode`
        );
    }

    initialize() {
        // On controller initialization, apply system/user preference
        if (this.systemDarkMode()) {
            this.setMode("dark");
            this.toggleCheckboxTarget.checked = true;
        } else {
            this.setMode("light");
            this.toggleCheckboxTarget.checked = false;
        }
    }

    toggleTheme() {
        // On clicking the checkbox input, toggle the theme
        if (this.toggleCheckboxTarget.checked) {
            this.setMode("dark");
            localStorage.setItem("darkMode", "true");
        } else {
            this.setMode("light");
            localStorage.setItem("darkMode", "false");
        }
    }

    toggleThemeKeyboard(e) {
        // Allow keyboard control of theme toggle
        if (e.key === "Enter") {
            this.toggleCheckboxTarget.click();
        }
    }
}
