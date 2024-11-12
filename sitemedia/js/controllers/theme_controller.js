// controllers/theme_controller.js

import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["toggleLabel", "toggleCheckbox"];

    systemDarkMode() {
        // Check system and prior user selection for dark mode
        return (
            // url param for dark mode should override all
            new URLSearchParams(window.location.search).get("dark-mode") ||
            // next priority should be prior user selection
            window.localStorage.getItem("darkMode") === "true" ||
            // finally, fallback to system setting
            (window.localStorage.getItem("darkMode") === null &&
                window.matchMedia &&
                window.matchMedia("(prefers-color-scheme: dark)").matches)
        );
    }

    setMode(mode) {
        // Toggle light/dark mode using classes on html element
        this.element.classList.add(`${mode}-mode`);
        this.element.classList.remove(
            `${mode === "light" ? "dark" : "light"}-mode`
        );
    }

    toggleCheckboxTargetConnected() {
        // On checkbox connected, apply system/user preference
        if (this.systemDarkMode()) {
            this.setMode("dark");
            this.toggleCheckboxTargets.forEach(
                (target) => (target.checked = true)
            );
        } else {
            this.setMode("light");
            this.toggleCheckboxTargets.forEach(
                (target) => (target.checked = false)
            );
        }
    }

    toggleTheme(e) {
        // On clicking the checkbox input, toggle the theme
        if (e.currentTarget.checked) {
            this.setMode("dark");
            localStorage.setItem("darkMode", "true");
            this.toggleCheckboxTargets.forEach(
                (target) => (target.checked = true)
            );
        } else {
            this.setMode("light");
            localStorage.setItem("darkMode", "false");
            this.toggleCheckboxTargets.forEach(
                (target) => (target.checked = false)
            );
        }
    }

    toggleThemeKeyboard(e) {
        // Allow keyboard control of theme toggle
        if (e.key === "Enter") {
            // use e.currentTarget to ensure correct target is clicked
            e.currentTarget.click();
        }
    }
}
