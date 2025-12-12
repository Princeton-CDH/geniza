// controllers/description_controller.js
import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
    static targets = ["description", "selector"];
    static classes = ["hidden"];

    connect() {
        // set the description language to the user's preferred language first
        this.changeLanguage();
    }

    changeLanguage() {
        // change the description language by showing the selected one
        // and hiding the deselected ones
        const selectedLang = this.selectorTarget.value;
        this.descriptionTargets.forEach((description) => {
            if (description.getAttribute("lang") === selectedLang) {
                description.classList.remove(this.hiddenClass);
            } else {
                description.classList.add(this.hiddenClass);
            }
        });
    }
}
