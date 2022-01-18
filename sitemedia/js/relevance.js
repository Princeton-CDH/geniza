// Script to make search query text a required field when "relevance" sort is selected

queryField = document.querySelector("input[name='q']");
sortRadioButtons = document.querySelectorAll("input[name='sort']");
relevanceSort = document.querySelector("input[name='sort'][value='relevance']");

// If "relevance" selected on page load, set query text required
if (relevanceSort.checked) {
    queryField.setAttribute("required", "required");
}

// When any radio button is changed, checked if "relevance" is selected
sortRadioButtons.forEach((radioButton) => {
    radioButton.addEventListener("change", () => {
        if (relevanceSort.checked) {
            queryField.setAttribute("required", "required");
        } else {
            queryField.removeAttribute("required");
        }
    });
});
