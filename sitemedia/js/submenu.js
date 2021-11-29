// Better menu animation when JS enabled

function addClass(target, className) {
    if (target) {
        target.classList.add(className);
    }
    return false;
}
const mainMenu = document.querySelector("ul#menu");
const menuButtons = mainMenu.querySelectorAll("a[role=button]");
Array.prototype.forEach.call(menuButtons, function (el) {
    if (el.parentNode.parentNode.id === "about-menu") {
        // Slide about menu out to the right
        el.addEventListener("click", () => {
            addClass(el.parentNode.parentNode, "slideout-right-mobile");
        });
    } else {
        // Slide main menu out to the left
        el.addEventListener("click", () => {
            addClass(el.parentNode.parentNode, "slideout-left-mobile");
        });
    }
});

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
        // Animate main menu closing on opening submenu
        addClass(mainMenu, "slideout-left-mobile");
        return false;
    });
});
