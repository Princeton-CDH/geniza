// src/controllers/search.js
import { Controller } from "@hotwired/stimulus";
import { ApplicationController, useDebounce } from "stimulus-use";

export default class extends Controller {
    static targets = ["query", "sort", "sortlabel"];
    static debounces = ["submit"];

    connect() {
        this.defaultSort = "scholarship_desc";
        useDebounce(this);
    }

    submit() {
        console.log("submitting the form");
        this.element.submit();
    }

    sortTargetConnected(element) {
        // when sort targets are first connected,
        // check and disable relevance sort if appropriate
        this.updateSort();
    }

    updateSort() {
        console.log("updateSort");
        // when query is empty, disable sort by relevance
        if (this.queryTarget.value.trim() == "") {
            this.disableRelevanceSort();
        } else {
            this.sortByRelevance();
        }
    }

    sortByRelevance() {
        this.sortTargets.forEach((radio) => {
            // enable and check relevance sort
            if (radio.value === "relevance") {
                radio.checked = true;
                radio.disabled = false;
                radio.ariaDisabled = false;
                this.setSortLabel(radio.parentElement.textContent);
            } // disable all other buttons
            else {
                radio.checked = false;
            }
        });
    }

    setSortLabel(label) {
        this.sortlabelTarget.children[0].innerHTML = label;
    }

    disableRelevanceSort() {
        this.sortTargets.forEach((radio) => {
            // uncheck and disable relevance sort option
            if (radio.value === "relevance") {
                radio.checked = false;
                radio.disabled = true;
                radio.ariaDisabled = true;
            }
            // if relevance sort was checked, set back to default
            else if (
                // this.relevanceSortElement.checked &&
                radio.value === this.defaultSort
            ) {
                radio.checked = true;
                this.setSortLabel(radio.parentElement.textContent);
            }
        });
    }
}
