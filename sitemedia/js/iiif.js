import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";

const application = Application.start();
const context = require.context(
    "./controllers",
    true,
    // only require iiif and transcription controllers
    /(iiif|transcription)_controller\.js$/
);
application.load(definitionsFromContext(context));
