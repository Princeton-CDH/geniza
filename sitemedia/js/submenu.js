// Adapted from W3C web accessibility tutorials:
// https://www.w3.org/WAI/tutorials/menus/flyout/#flyoutnavkbfixed

const menuItems = document.querySelectorAll("li.has-submenu");
Array.prototype.forEach.call(menuItems, function (el) {
    el.querySelector("a").addEventListener("click", function () {
        if (this.parentNode.className == "menu-item has-submenu") {
            this.parentNode.className = "menu-item has-submenu open";
            this.setAttribute("aria-expanded", "true");
        } else {
            this.parentNode.className = "menu-item has-submenu";
            this.setAttribute("aria-expanded", "false");
        }
        return false;
    });
});
