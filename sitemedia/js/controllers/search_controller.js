// controllers/search_controller.js

import { Controller } from "@hotwired/stimulus";
import { ApplicationController, useDebounce } from "stimulus-use";
import * as Turbo from "@hotwired/turbo";

export default class extends Controller {
    static targets = [
        "query",
        "sort",
        "filterModal",
        "filtersButton",
        "dateRange",
        "doctypeFilter",
        "dropdownDetails",
        "helpDialog",
        "maxYear",
        "minYear",
        "placeFiltersCheckbox",
        "placesMode",
        "peopleMode",
        "radioSort",
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
        const searchPage = this.element.dataset.page;
        window.sessionStorage.setItem(`${searchPage}-filters-expanded`, "true");
    }

    toggleFiltersOpen(e) {
        // toggle filters modal/panel open and closed
        if (!e.currentTarget.closest('label[for="place-filters"]')) {
            e.preventDefault();
            e.currentTarget.classList.toggle("open");
        }
        const filtersOpen =
            this.filterModalTarget.getAttribute("aria-expanded");
        const newFiltersOpen = filtersOpen === "true" ? "false" : "true";
        this.filterModalTarget.setAttribute("aria-expanded", newFiltersOpen);
        const searchPage = this.element.dataset.page;
        window.sessionStorage.setItem(
            `${searchPage}-filters-expanded`,
            newFiltersOpen
        );
    }

    closeFilters(e) {
        // close filter modal / panel if open
        e.preventDefault();
        this.filterModalTarget.setAttribute("aria-expanded", "false");
        const searchPage = this.element.dataset.page;
        window.sessionStorage.setItem(
            `${searchPage}-filters-expanded`,
            "false"
        );
        if (this.hasFiltersButtonTarget) {
            this.filtersButtonTarget.classList.remove("open");
        }
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
            if (savedFilterState === "true") {
                if (this.hasFiltersButtonTarget) {
                    this.filtersButtonTarget.classList.add("open");
                } else if (this.hasPlaceFiltersCheckboxTarget) {
                    this.placeFiltersCheckboxTarget.checked = true;
                }
            }
        }
    }

    unapplyFilter(e) {
        // unapply a filter by field and value pair
        const filterName = e.currentTarget.dataset.field;
        const filterValue = e.currentTarget.value;
        const searchParams = new URLSearchParams(window.location.search);
        if (searchParams.has(filterName, filterValue)) {
            let selector = `value*="${filterValue}"`;
            if (filterValue === "on") {
                selector = "checked";
            }
            let appliedFilter = this.filterModalTarget.querySelector(
                `label[for*="${filterName}"] input[${selector}]`
            );
            if (appliedFilter) {
                appliedFilter.checked = false;
            } else {
                appliedFilter = this.filterModalTarget.querySelector(
                    `label[for*="${filterName}"] option[${selector}]`
                );
                appliedFilter.selected = false;
            }
        } else if (
            ["date_range", "docdate"].includes(filterName) &&
            (searchParams.has("date_range_0") ||
                searchParams.has("date_range_1") ||
                searchParams.has("docdate_0") ||
                searchParams.has("docdate_1"))
        ) {
            // special handling for date range filter
            const appliedFilters = this.filterModalTarget.querySelectorAll(
                `label[for*="${filterName}"] input`
            );
            appliedFilters.forEach((f) => (f.value = ""));
        }
    }

    clearFilters(e) {
        // clear all filters
        e.preventDefault();
        const appliedFilters =
            this.filterModalTarget.querySelectorAll("input[checked]");
        appliedFilters.forEach((f) => (f.checked = false));
        const dateFilters = this.filterModalTarget.querySelectorAll(
            "input[type='number']"
        );
        dateFilters.forEach((f) => (f.value = ""));
        this.element.requestSubmit();
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

    sortByRelevance(radio = false) {
        if (radio && !this.relevanceSortElement.checked) {
            this.relevanceSortElement.checked = true;
            this.relevanceSortDirectionElement.checked = true;
            this.dropdownDetailsTarget.querySelector("summary").textContent =
                this.relevanceSortLabel;
        } else if (!radio) {
            this.sortTarget.value = this.relevanceSortElement.value;
        }
        this.relevanceSortElement.disabled = false;
        this.relevanceSortElement.ariaDisabled = false;
    }

    disableRelevanceSort(radio = false) {
        // if relevance sort was selected, set back to default
        if (radio && this.relevanceSortElement.checked) {
            this.relevanceSortElement.checked = false;
            this.defaultSortElement.checked = true;
            this.defaultSortDirectionElement.checked = true;
            this.dropdownDetailsTarget.querySelector("summary").textContent =
                this.defaultSortLabel;
        } else if (
            !radio &&
            this.sortTarget.value == this.relevanceSortElement.value
        ) {
            this.sortTarget.value = this.defaultSortElement.value;
        }
        // disable relevance sort
        this.relevanceSortElement.disabled = true;
        this.relevanceSortElement.ariaDisabled = true;
    }

    radioSortTargetConnected() {
        // similar to sortTargetConnected, but handled differently for radio inputs
        // as their DOM structure is different
        const sortOptions = Array.from(
            this.radioSortTarget.querySelectorAll("input")
        );
        this.relevanceSortElement = sortOptions.find(
            (target) => target.value === "relevance"
        );
        // a search using radio input elements is only doing so because it is split into
        // separate fields for sort field and direction, so handle direction too
        this.relevanceSortDirectionElement = sortOptions.find(
            (target) => target.value === "desc"
        );
        // keep track of labels since they aren't stored on the input elements
        this.relevanceSortLabel = this.radioSortTarget.querySelector(
            `label[for=${this.relevanceSortElement.id}]`
        ).textContent;
        this.defaultSortElement = sortOptions.find(
            (target) => target.value === "name"
        );
        this.defaultSortDirectionElement = sortOptions.find(
            (target) => target.value === "asc"
        );
        this.defaultSortLabel = this.radioSortTarget.querySelector(
            `label[for=${this.defaultSortElement.id}]`
        ).textContent;
        this.autoUpdateRadioSort();
    }

    autoUpdateRadioSort(event) {
        // when query is empty, disable sort by relevance
        if (this.queryTarget.value.trim() == "") {
            this.disableRelevanceSort(true);
        } else if (event && this.defaultSortElement.checked) {
            // if this was triggered by an event and not in sortTargetConnected,
            // and the sort is currently the default, sort by relevance
            this.sortByRelevance(true);
        }
    }

    clickCloseDropdown(e) {
        // Event listener to close the list view sort dropdown <details> element when a click is
        // registered outside of it. This needs to be on the whole document because the click could
        // be from anywhere!
        this.dropdownDetailsTargets.forEach((target) => {
            if (target.open && !target.contains(e.target)) {
                target.removeAttribute("open");
            }
        });
    }

    preventEnterKeypress(e) {
        // text input elements like the date range will try to click buttons in the form
        // if Enter is pressed while they are focused, so prevent that behavior
        if (e.key === "Enter") {
            e.preventDefault();
        }
    }

    toggleHelpDialog() {
        // open or close the help dialog modal
        if (this.helpDialogTarget.open) {
            this.helpDialogTarget.close();
        } else {
            this.helpDialogTarget.showModal();
        }
    }

    onToggleMap(e) {
        // for the places list page, handle toggling the map on and off on mobile
        if (!e.currentTarget.checked) {
            this.scrollMobilePlaces();
        }
        window.sessionStorage.setItem("places-list-view", e.target.checked);
    }

    placesModeTargetConnected() {
        // Saved mode state should persist when connected
        let isPlacesListMode =
            window.sessionStorage.getItem("places-list-view");
        if (isPlacesListMode === "true") {
            this.placesModeTarget.querySelector(
                "input[type='checkbox']"
            ).checked = true;
        }
        this.scrollMobilePlaces();
    }

    scrollMobilePlaces() {
        // for the mobile places list page, scroll to the top on load if the map is visible
        const isMobile = window.innerWidth <= 900;
        if (isMobile) {
            window.scrollTo({ top: 0 });
        }
    }

    // person list view mode checkbox
    togglePeopleViewMode(e) {
        // save in session storage
        window.sessionStorage.setItem("people-list-view", e.target.checked);
    }

    peopleModeTargetConnected() {
        // Saved mode state should persist when connected
        let isPeopleListMode =
            window.sessionStorage.getItem("people-list-view");
        if (isPeopleListMode === "true") {
            this.peopleModeTarget.checked = true;
        }
    }

    updateTimeline(e) {
        e.target.parentNode.style.setProperty(
            `--${e.target.id}`,
            +e.target.value
        );
        const val = parseInt(e.target.value);
        const isMin = e.target === this.minYearTarget;
        const otherThumbVal = parseInt(
            isMin ? this.maxYearTarget.value : this.minYearTarget.value
        );
        if (val < otherThumbVal) {
            this.dateRangeTargets[0].value = val;
            this.dateRangeTargets[1].value = otherThumbVal;
        } else {
            this.dateRangeTargets[0].value = otherThumbVal;
            this.dateRangeTargets[1].value = val;
        }
    }
}
