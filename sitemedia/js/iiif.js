import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";
import * as Turbo from "@hotwired/turbo";

const application = Application.start();
// only require iiif_controller.js
const context = require.context("./controllers", true, /iiif_controller\.js$/);
application.load(definitionsFromContext(context));
