// Better menu animation when JS enabled

function closeAboutMenu() {
    aboutMenu = document.querySelector("ul#about-menu");
    if (aboutMenu && !aboutMenu.classList.contains("slideout-right-mobile")) {
        aboutMenu.classList.add("slideout-right-mobile");
    }
    return false;
}
function closeMainMenu(mainMenu) {
    if (mainMenu && !mainMenu.classList.contains("slideout-left-mobile")) {
        mainMenu.classList.add("slideout-left-mobile");
    }
    return false;
}

let mainMenu = document.querySelector("ul#menu");
mainMenu
    .querySelector("a.home-link")
    .addEventListener("click", () => closeMainMenu(mainMenu));
mainMenu
    .querySelector("a#close-main-menu")
    .addEventListener("click", () => closeMainMenu(mainMenu));

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
        mainMenu = this.parentNode.parentNode;
        closeMainMenu(mainMenu);
        return false;
    });
    // Animate submenu closing on clicking relevant buttons
    el.querySelector("a#back-to-main-menu").addEventListener(
        "click",
        closeAboutMenu
    );
    el.querySelector("a#close-about-menu").addEventListener(
        "click",
        closeAboutMenu
    );
});
