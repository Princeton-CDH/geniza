import { Controller } from "@hotwired/stimulus";

// Controller for handling alert events and displaying "toast" alerts with their message contents.
// used with tahqiq for now, but could be extended to other types of alert events.
export default class extends Controller {
    initialize() {
        // bind "this" so we can append elements
        this.boundAlertHandler = this.handleAlert.bind(this);
    }
    connect() {
        // avoid adding a duplicate event listener, it happens sometimes(?)
        // regardless of the number of images on the page; bound to alerts
        // div in document_transcribe.html... TODO: figure out why
        if (!this.element.alertListenerInitialized) {
            document.addEventListener("tahqiq-alert", this.boundAlertHandler);
            this.element.alertListenerInitialized = true;
        }
    }
    disconnect() {
        document.removeEventListener("tahqiq-alert", this.boundAlertHandler);
    }
    handleAlert(evt) {
        // create a new div with the alert message and appropriate classes
        const { message, status } = evt.detail;
        const alert = document.createElement("div");
        alert.textContent = message;
        alert.className = "alert alert-visible";
        if (status) {
            alert.classList.add(`alert-${status}`);
        }

        // append the alert as child of alerts div
        this.element.appendChild(alert);

        // longer timeout for error messages for readability
        const timeout = status === "error" ? 5000 : 3000;

        // remove visible class after timeout
        setTimeout(() => {
            alert.classList.remove("alert-visible");
        }, timeout);

        // remove child after transition completes (+350ms)
        setTimeout(() => {
            this.element.removeChild(alert);
        }, timeout + 350);
    }
}
