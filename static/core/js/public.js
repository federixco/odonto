/* Mejoras progresivas: enlaces, formularios y acordeones funcionan sin JS. */
(() => {
    "use strict";
    const menuButton = document.querySelector(".menu-toggle");
    const navigation = document.querySelector("#navegacion");
    if (menuButton && navigation) {
        document.documentElement.classList.add("nav-enhanced");
        menuButton.hidden = false;
        const closeMenu = () => {
            menuButton.setAttribute("aria-expanded", "false");
            navigation.classList.remove("is-open");
        };
        menuButton.addEventListener("click", () => {
            const expanded = menuButton.getAttribute("aria-expanded") === "true";
            menuButton.setAttribute("aria-expanded", String(!expanded));
            navigation.classList.toggle("is-open", !expanded);
        });
        navigation.addEventListener("click", (event) => {
            if (event.target.closest("a")) closeMenu();
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && navigation.classList.contains("is-open")) {
                closeMenu();
                menuButton.focus();
            }
        });
        document.addEventListener("click", (event) => {
            if (!event.target.closest(".header-inner")) closeMenu();
        });
        window.matchMedia("(min-width: 861px)").addEventListener("change", closeMenu);
    }
    // Solo alterna la visibilidad; no almacena ni transmite la contraseña.
    document.querySelectorAll("[data-password-toggle]").forEach((button) => {
        const input = document.getElementById(button.getAttribute("aria-controls"));
        if (!input) return;
        button.hidden = false;
        button.addEventListener("click", () => {
            const show = input.type === "password";
            input.type = show ? "text" : "password";
            button.textContent = show ? "Ocultar" : "Mostrar";
            button.setAttribute("aria-pressed", String(show));
            if (button.dataset.passwordLabel) {
                button.setAttribute("aria-label", button.textContent + " " + button.dataset.passwordLabel);
            }
        });
    });
})();
