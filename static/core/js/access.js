/* Presentación de errores de servidor; no intercepta ni valida formularios. */
(() => {
    "use strict";
    const page = document.querySelector(".access-page");
    if (!page) return;
    page.querySelectorAll(".has-error").forEach((field) => {
        const input = field.querySelector("input");
        const errors = field.querySelector(".access-field-errors");
        if (!input || !errors) return;
        input.setAttribute("aria-invalid", "true");
        const descriptions = new Set((input.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
        descriptions.add(errors.id);
        input.setAttribute("aria-describedby", [...descriptions].join(" "));
    });
    const summary = page.querySelector(".form-errors");
    if (summary) summary.focus();
})();
