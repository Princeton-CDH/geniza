import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";

const application = Application.start();
// only require annotation_controller.js
const context = require.context(
    "./controllers",
    true,
    /annotation_controller\.js$/
);
application.load(definitionsFromContext(context));
