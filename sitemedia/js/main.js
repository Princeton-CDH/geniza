import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";
import * as Turbo from "@hotwired/turbo";

const application = Application.start();
// NOTE: Any new controllers that should not be part of this bundle must be explicitly excluded
const context = require.context(
    "./controllers",
    true,
    // exclude alert, annotation, iiif, and transcription controllers using negative lookahead
    /^.*\/(?!iiif)(?!annotation)(?!alert)(?!transcription).*_controller.*\.js$/
);
application.load(definitionsFromContext(context));

// Workarounds to get document details page to scroll to top on "advance" visit;
// this has a side effect of losing scroll position on navigating "back", so save
// scroll position before cache and restore it before visit (if visit type is restore)

function saveScrollPosition() {
    document.body.dataset.scrollPosition = JSON.stringify([
        window.scrollX,
        window.scrollY,
    ]);
}
function restoreScrollPosition(event) {
    const scrollPosition = JSON.parse(
        document.body.dataset.scrollPosition || "[]"
    );
    if (scrollPosition && event.detail.action == "restore") {
        window.scrollTo(...scrollPosition);
    } else if (event.detail.action === "advance") {
        window.scrollTo(0, 0);
    }
}

window.addEventListener("turbo:before-cache", saveScrollPosition);
window.addEventListener("turbo:visit", restoreScrollPosition);

// Test banner/ribbon dismiss functionality
const ribbon = document.querySelector(".ribbon");
if (ribbon) {
    const faded = sessionStorage.getItem("fade-test-banner", true);
    if (!faded) {
        document.querySelector(".ribbon-box").classList.remove("fade");
    }
    ribbon.addEventListener("click", function () {
        document.querySelector(".ribbon-box").classList.add("fade");
        sessionStorage.setItem("fade-test-banner", true);
    });
}
