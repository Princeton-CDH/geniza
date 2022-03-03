import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";
import * as Turbo from "@hotwired/turbo";

const application = Application.start();
const context = require.context("./controllers", true, /\.js$/);
application.load(definitionsFromContext(context));

/* turbo event debug  */

function logvisit(event) {
    let msg = "accessing " + event.detail.url;
    if (event.detail.action != undefined) {
        msg = msg + " with " + event.detail.action;
    }
    console.log(msg);
}

function logclick(event) {
    console.log("clicking " + event.detail.url);
}

function logload(event) {
    console.log("turbo loaded");
    console.log(event);
}

function logframeload(event) {
    console.log("turbo frame loaded");
    console.log(event.target);
}

function logBeforeRender(event) {
    console.log("turbo before-render");
    console.log(event.detail.newBody);
}

function logBeforeCache(event) {
    console.log("turbo before-cache");
    console.log(event);
}

function logHashChange(event) {
    console.log("turbo hashchange event");
    console.log(event.oldURL);
    console.log(event.newURL);
}

window.addEventListener("turbo:visit", logvisit);
window.addEventListener("turbo:before-visit", logvisit);
window.addEventListener("turbo:click", logclick);
window.addEventListener("turbo:load", logload);
window.addEventListener("turbo:frame-load", logframeload);
window.addEventListener("turbo:before-render", logBeforeRender);
window.addEventListener("turbo:before-cache", logBeforeCache);
window.addEventListener("hashchange", logHashChange);
