// Adapted from W3C web accessibility tutorials:
// https://www.w3.org/WAI/tutorials/menus/flyout/#flyoutnavkbfixed

const menuItems = document.querySelectorAll("li.has-submenu");
Array.prototype.forEach.call(menuItems, function (el) {
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
});
