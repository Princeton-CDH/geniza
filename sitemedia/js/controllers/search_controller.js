// controllers/search_controller.js

import { Controller } from "@hotwired/stimulus";
import { ApplicationController, useDebounce } from "stimulus-use";
import * as Turbo from "@hotwired/turbo";

export default class extends Controller {
    static targets = ["query", "sort", "sortlabel", "filterModal"];
    static debounces = ["update"];

    connect() {
        useDebounce(this);
    }

    update() {
        // submit the form and update the search results
        this.navBackToSearch();
        // NOTE: turbo needs requestSubmit instead of submit to catch the event properly!
        // see https://discuss.hotwired.dev/t/triggering-turbo-frame-with-js/1622/15
        this.element.requestSubmit();
    }

    // Open/close the filter modal using aria-expanded instead of targeting with a link, to prevent
    // scroll jumping around the page. Will still work as a link when JS is disabled.
    openFilters(e) {
        e.preventDefault();
        this.filterModalTarget.setAttribute("aria-expanded", "true");
    }

    closeFilters(e) {
        e.preventDefault();
        this.filterModalTarget.setAttribute("aria-expanded", "false");
        this.navBackToSearch();
    }

    filterModalTargetConnected() {
        // expanded state should persist when connected
        console.log("connected. aria-expanded:");
        console.log(this.filterModalTarget.getAttribute("aria-expanded"));
        // could there be a way to update counts here??
    }

    navBackToSearch() {
        // Close filter modal if open. If the window location is #filters (i.e. filter modal is
        // open), submitting the form will reopen it, so the location must be set back to # in
        // order for the "apply" button in the filter modal to close the modal.
        if (Turbo.navigator.location.href.includes("#filters")) {
            // ensure filters modal can be closed if on #filters URL
            Turbo.visit("#");
        }
    }

    sortTargetConnected() {
        // when sort targets are first connected,
        // check and disable relevance sort if appropriate
        this.relevanceSortElement = this.sortTargets.find(
            (target) => target.value === "relevance"
        );
        this.defaultSortElement = this.sortTargets.find(
            (target) => target.value === "random"
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
