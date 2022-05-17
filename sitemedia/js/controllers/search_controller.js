// controllers/search_controller.js

import { Controller } from "@hotwired/stimulus";
import { ApplicationController, useDebounce } from "stimulus-use";
import * as Turbo from "@hotwired/turbo";

export default class extends Controller {
    static targets = [
        "query",
        "sort",
        "sortLabel",
        "sortDetails",
        "filterModal",
        "doctypeFilter",
    ];
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
        window.sessionStorage.setItem("filters-expanded", "true");
    }

    closeFilters(e) {
        e.preventDefault();
        this.filterModalTarget.setAttribute("aria-expanded", "false");
        window.sessionStorage.setItem("filters-expanded", "false");
        this.navBackToSearch();
    }

    filterModalTargetConnected() {
        // Expanded/collapsed state should persist when connected
        let savedFilterState =
            window.sessionStorage.getItem("filters-expanded");
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

    // Sort element functions

    changeSort(e) {
        /*
         * Event listener to mimic <select> menu "header" functionality in a details/summary with radio
         * button inputs. Without this, the radio buttons will still work, but changes to the selected
         * option will not be visible in the collapsed <summary> until the form is submitted and the page
         * reloads.
         */
        this.setSortLabel(e.currentTarget.parentElement.textContent);
    }

    setSortLabel(label) {
        this.sortLabelTarget.children[0].innerHTML = label;
    }

    keyboardCloseSort(e) {
        // exit the list and submit on enter/space
        if (
            this.sortDetailsTarget.open &&
            (e.code === "Enter" ||
                e.code === "Space" ||
                (!e.shiftKey && e.code === "Tab")) // Tab out of a radio button = exiting the list
        ) {
            this.sortDetailsTarget.removeAttribute("open");
        }
    }

    shiftTabCloseSort(e) {
        // Shift-tab out of the summary = exiting the list
        if (this.sortDetailsTarget.open && e.shiftKey && e.code === "Tab") {
            this.sortDetailsTarget.removeAttribute("open");
        }
    }

    clickCloseSort(e) {
        // Event listener to close the sort <details> element when a click is registered outside
        // of it. This needs to be on the whole document because the click could be from anywhere!
        if (
            this.sortDetailsTarget.open &&
            !this.sortDetailsTarget.contains(e.target)
        ) {
            this.sortDetailsTarget.removeAttribute("open");
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
        this.autoUpdateSort();
    }

    autoUpdateSort(event) {
        // when query is empty, disable sort by relevance
        if (this.queryTarget.value.trim() == "") {
            this.disableRelevanceSort();
        } else if (event) {
            // if this was triggered by an event and not in sortTargetConnected,
            // and the sort is currently the default, sort by relevance
            if (this.defaultSortElement.checked) {
                this.sortByRelevance();
            }
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
