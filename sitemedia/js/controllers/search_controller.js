// src/controllers/search.js

import { Controller } from "@hotwired/stimulus";
import { ApplicationController, useDebounce } from "stimulus-use";

export default class extends Controller {
    static targets = ["query", "sort", "sortlabel"];
    static debounces = ["submit"];

    connect() {
        useDebounce(this);
    }

    submit() {
        this.element.submit();
    }

    sortTargetConnected() {
        // when sort targets are first connected,
        // check and disable relevance sort if appropriate
        this.relevanceSortElement = this.sortTargets.find(
            (target) => target.value === "relevance"
        );
        this.defaultSortElement = this.sortTargets.find(
            (target) => target.value === "scholarship_desc"
        );
        this.updateSort();
    }

    updateSort(event) {
        // when query is empty, disable sort by relevance
        if (this.queryTarget.value.trim() == "") {
            this.disableRelevanceSort();
            // if this was triggered by an event and not in sortTargetConnected, sort by relevance
        } else if (event) {
            this.sortByRelevance();
        }
    }

    sortByRelevance() {
        this.relevanceSortElement.checked = true;
        this.relevanceSortElement.disabled = false;
        this.relevanceSortElement.ariaDisabled = false;
        this.setSortLabel(this.relevanceSortElement.parentElement.textContent);
        this.sortTargets
            .filter((el) => el.value !== "relevance")
            .forEach((radio) => {
                radio.checked = false;
            });
    }

    setSortLabel(label) {
        this.sortlabelTarget.children[0].innerHTML = label;
    }

    disableRelevanceSort() {
        // if relevance sort was checked, set back to default
        if (this.relevanceSortElement.checked) {
            this.relevanceSortElement.checked = false;
            this.defaultSortElement.checked = true;
            this.setSortLabel(
                this.defaultSortElement.parentElement.textContent
            );
        }
        // disable relevance sort
        this.relevanceSortElement.disabled = true;
        this.relevanceSortElement.ariaDisabled = true;
    }
}
