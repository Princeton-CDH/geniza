/*
 * JS to improve search form functionality
 */

/*
 * Script to make the sort menu details/summary act more like a <select> in JS environments
 */

const details = document.querySelector("details.sort-select");
const summarySpan = details.querySelector("summary span");
const radioButtons = document.querySelectorAll("input[name='sort']");
radioButtons.forEach((radio) => {
    /*
     * Event listener to mimic <select> menu "header" functionality in a details/summary with radio
     * button inputs. Without this, the radio buttons will still work, but changes to the selected
     * option will not be visible in the collapsed <summary> until the form is submitted and the page
     * reloads.
     */
    radio.addEventListener("change", () => {
        if (radio.checked) {
            // Set <summary> label to the label of the checked button
            summarySpan.innerHTML = radio.parentElement.textContent;
        }
    });
    /*
     * Event listeners to close the <details> element when an item is chosen, either by clicking or
     * via keypresses Space, Enter, or Tab. Without this, the <details> can still be closed by
     * clicking on its summary.
     */
    radio.addEventListener("keydown", (e) => {
        if (
            e.code === "Enter" ||
            e.code === "Space" ||
            (!e.shiftKey && e.code === "Tab")
        ) {
            if (details.open) {
                e.preventDefault(); // Prevent the form from being submitted
                details.removeAttribute("open");
            }
        }
    });
    radio.parentElement.addEventListener("mouseup", () => {
        if (details.open) details.removeAttribute("open");
    });
    // Tab out of a radio button = exiting the list
});

/*
 * Event listeners to close the <details> element when a click is registered outside of it, or when
 * a user tabs out of it.
 * Without this, the <details> can still be closed by clicking on its summary.
 */
document.addEventListener("click", (e) => {
    if (details.open && !details.contains(e.target)) {
        details.removeAttribute("open");
    }
});
details.querySelector("summary").addEventListener("keydown", (e) => {
    // Shift-tab out of the summary = exiting the list
    if (details.open && e.shiftKey && e.code === "Tab") {
        details.removeAttribute("open");
    }
});

/*
 * Event listener to
 *
 *
 */

const textInput = document.querySelector("input[type='search']");
const relevanceCheckbox = document.querySelector(
    "input[name='sort'][value='relevance']"
);

function onTextInputChange() {
    // update sort options based on changes to text input fields
    // adapted from ppa-django

    // if any text inputs now have content
    if (textInput.value.trim() !== "") {
        radioButtons.forEach((radio) => {
            // enable and check relevance sort
            if (radio.value === "relevance") {
                radio.checked = true;
                radio.disabled = false;
                radio.ariaDisabled = false;
                summarySpan.innerHTML = radio.parentElement.textContent;
            }
            // disable all other buttons
            else {
                radio.checked = false;
            }
        });

        // no text inputs have content now
    } else {
        let relevanceWasChecked = relevanceCheckbox.checked;
        radioButtons.forEach((radio) => {
            // uncheck and disable relevance sort option
            if (radio.value === "relevance") {
                radio.checked = false;
                radio.disabled = true;
                radio.ariaDisabled = true;
            }
            // if relevance sort was checked, set back to scholarship_desc
            else if (
                relevanceWasChecked &&
                radio.value === "scholarship_desc"
            ) {
                radio.checked = true;
                summarySpan.innerHTML = radio.parentElement.textContent;
            }
        });
    }
}

// Add on any input change (keyboard input or clear)
textInput.addEventListener("input", onTextInputChange);

// Run once on page load to disable relevance (if search box is empty)
onTextInputChange();
