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

const setMode = (mode) => {
    if (mode === "dark") {
        body.classList.add("dark-mode");
        body.classList.remove("light-mode");
        if (typeof miradorInstance !== "undefined" && miradorInstance) {
            let action = Mirador.actions.updateConfig({
                selectedTheme: "dark",
            });
            miradorInstance.store.dispatch(action);
        }
    } else if (mode === "light") {
        body.classList.add("light-mode");
        body.classList.remove("dark-mode");
        if (typeof miradorInstance !== "undefined" && miradorInstance) {
            let action = Mirador.actions.updateConfig({
                selectedTheme: "light",
            });
            miradorInstance.store.dispatch(action);
        }
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
