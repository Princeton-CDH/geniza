// Script to toggle light and dark mode themes via a checkbox input

// Check system and prior user selection for dark mode
const systemDarkMode =
    window.localStorage.getItem("darkMode") === "true" ||
    (window.localStorage.getItem("darkMode") === null &&
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);

const body = document.querySelector("body");
const toggleLabel = document.querySelector("label#theme-toggle");
const toggleCheckbox = toggleLabel.querySelector("input");

if (systemDarkMode) {
    body.classList.add("dark-mode");
    body.classList.remove("light-mode");
    toggleCheckbox.checked = true;
} else {
    body.classList.add("light-mode");
    body.classList.remove("dark-mode");
    toggleCheckbox.checked = false;
}

// Toggle using classes on body element
toggleCheckbox.addEventListener("change", function () {
    if (toggleCheckbox.checked) {
        body.classList.add("dark-mode");
        body.classList.remove("light-mode");
        localStorage.setItem("darkMode", "true");
    } else {
        body.classList.add("light-mode");
        body.classList.remove("dark-mode");
        localStorage.setItem("darkMode", "false");
    }
});

// Allow keyboard control of above
toggleLabel.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
        toggleCheckbox.click();
    }
});
