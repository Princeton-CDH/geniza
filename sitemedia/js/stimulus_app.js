import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";
import * as Turbo from "@hotwired/turbo";

const application = Application.start();
const context = require.context("./controllers", true, /\.js$/);
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
