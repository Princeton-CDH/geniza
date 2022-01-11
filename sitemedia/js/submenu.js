// Adapted from W3C web accessibility tutorials:
// https://www.w3.org/WAI/tutorials/menus/flyout/#flyoutnavkbfixed

const menuItems = document.querySelectorAll("li.has-submenu");
Array.prototype.forEach.call(menuItems, function (el) {
    // Add/remove "open" class, aria-expanded attr on click
    el.querySelector("a").addEventListener("click", function () {
        if (this.parentNode.classList.contains("open")) {
            this.setAttribute("aria-expanded", "false");
            this.parentNode.classList.remove("open");
        } else {
            this.setAttribute("aria-expanded", "true");
            this.parentNode.classList.add("open");
        }
        return false;
    });
    // Modify aria-expanded on mouseover/mouseout
    el.addEventListener("mouseover", function () {
        const link = this.querySelector("a");
        if (link.getAttribute("aria-expanded") === "false") {
            link.setAttribute("aria-expanded", "true");
        }
        return false;
    });
    el.addEventListener("mouseout", function () {
        const link = this.querySelector("a");
        if (link.getAttribute("aria-expanded") === "true") {
            link.setAttribute("aria-expanded", "false");
        }
        return false;
    });
});
