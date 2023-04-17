import { Application } from "@hotwired/stimulus";
import { definitionsFromContext } from "@hotwired/stimulus-webpack-helpers";

const application = Application.start();
const context = require.context(
    "./controllers",
    true,
    // only require iiif, transcription, ittpanel controllers
    /(iiif|transcription|ittpanel)_controller\.js$/
);
application.load(definitionsFromContext(context));
