// controllers/search_controller.js

import { Controller } from "@hotwired/stimulus";
import { ApplicationController, useDebounce } from "stimulus-use";
import * as Turbo from "@hotwired/turbo";

export default class extends Controller {
    static targets = ["query", "sort", "filterModal", "doctypeFilter"];
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
    // Saves expanded/collapsed state in session storage.
    openFilters(e) {
        e.preventDefault();
        this.filterModalTarget.setAttribute("aria-expanded", "true");
        const searchPage = this.element.dataset.page;
        window.sessionStorage.setItem(`${searchPage}-filters-expanded`, "true");
    }

    closeFilters(e) {
        e.preventDefault();
        this.filterModalTarget.setAttribute("aria-expanded", "false");
        const searchPage = this.element.dataset.page;
        window.sessionStorage.setItem(
            `${searchPage}-filters-expanded`,
            "false"
        );
        this.navBackToSearch();
    }

    filterModalTargetConnected() {
        // Expanded/collapsed state should persist when connected
        const searchPage = this.element.dataset.page;
        let savedFilterState = window.sessionStorage.getItem(
            `${searchPage}-filters-expanded`
        );
        if (savedFilterState) {
            this.filterModalTarget.setAttribute(
                "aria-expanded",
                savedFilterState
            );
        }
    }

    // doctype filter <details> element
    toggleDoctypeFilter() {
        // "open" attribute is null when collapsed, empty string when open
        let currentState =
            this.doctypeFilterTarget.getAttribute("open") !== null;
        // toggling will reverse this state
        let stateAfterClicked = !currentState;
        // save in session storage
        window.sessionStorage.setItem(
            "doctype-filter-expanded",
            stateAfterClicked
        );
    }

    doctypeFilterTargetConnected() {
        // Expanded/collapsed state should persist when connected
        let savedDoctypeState = window.sessionStorage.getItem(
            "doctype-filter-expanded"
        );
        if (savedDoctypeState === "true") {
            this.doctypeFilterTarget.setAttribute("open", "");
        }
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

    applyFilters(e) {
        // The apply button needs to close the filter modal on mobile before submitting
        e.preventDefault();
        this.closeFilters(e);
        this.update();
    }

    // Sort element functions (enable/disable relevance)

    sortTargetConnected() {
        // when sort target is first connected,
        // disable relevance sort if appropriate
        this.relevanceSortElement = Array.from(this.sortTarget.options).find(
            (target) => target.value === "relevance"
        );
        this.defaultSortElement = Array.from(this.sortTarget.options).find(
            (target) => target.value === "random"
        );
        this.autoUpdateSort();
    }

    autoUpdateSort(event) {
        // when query is empty, disable sort by relevance
        if (this.queryTarget.value.trim() == "") {
            this.disableRelevanceSort();
        } else if (
            event &&
            this.sortTarget.value == this.defaultSortElement.value
        ) {
            // if this was triggered by an event and not in sortTargetConnected,
            // and the sort is currently the default, sort by relevance
            this.sortByRelevance();
        }
    }

    sortByRelevance() {
        this.sortTarget.value = this.relevanceSortElement.value;
        this.relevanceSortElement.disabled = false;
        this.relevanceSortElement.ariaDisabled = false;
    }

    disableRelevanceSort() {
        // if relevance sort was selected, set back to default
        if (this.sortTarget.value == this.relevanceSortElement.value) {
            this.sortTarget.value = this.defaultSortElement.value;
        }
        // disable relevance sort
        this.relevanceSortElement.disabled = true;
        this.relevanceSortElement.ariaDisabled = true;
    }
}
