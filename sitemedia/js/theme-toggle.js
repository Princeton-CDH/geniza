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

// Function to do shared actions for manual toggle and system light/dark mode
const setMode = (mode) => {
    body.classList.add(`${mode}-mode`);
    body.classList.remove(`${mode === "light" ? "dark" : "light"}-mode`);
    if (typeof miradorInstance !== "undefined" && miradorInstance) {
        const action = Mirador.actions.updateConfig({
            selectedTheme: mode,
        });
        miradorInstance.store.dispatch(action);
    }
};

if (systemDarkMode) {
    setMode("dark");
    toggleCheckbox.checked = true;
} else {
    setMode("light");
    toggleCheckbox.checked = false;
}

// Toggle using classes on body element
toggleCheckbox.addEventListener("change", function () {
    if (toggleCheckbox.checked) {
        setMode("dark");
        localStorage.setItem("darkMode", "true");
    } else {
        setMode("light");
        localStorage.setItem("darkMode", "false");
    }
});

// Allow keyboard control of above
toggleLabel.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
        toggleCheckbox.click();
    }
});
