"use strict";
// Resumen de presentación. Los formularios y las validaciones siguen en sus rutas originales.
document.addEventListener("DOMContentLoaded", () => {
    if (!document.body.classList.contains("confirmation-page")) return;
    document.querySelectorAll("[data-review-form]").forEach(form => {
        const dentist = form.querySelector("[data-derivante-selector]");
        const patient = form.querySelector("[data-paciente-selector]");
        const write = (selector, text) => {
            const node = form.querySelector(selector);
            if (node && node.textContent !== text) node.textContent = text;
        };
        function updateAccess() {
            const value = dentist?.querySelector("[data-selector-value]").value || "";
            const selection = dentist?.querySelector("[data-selector-selection]").textContent || "";
            const name = selection.startsWith("Seleccionado: ") ? selection.slice(14).split(" · ")[0] : "";
            const unavailable = selection.startsWith("Selección no disponible");
            write("[data-review-access]", value ? (name || (unavailable ? "Revisá el derivante" : "Verificando derivante…")) : "Sin derivante asignado");
            write("[data-review-access-detail]", value ? (unavailable ? "Elegí otro profesional habilitado" : "Publicación sujeta a verificación") : "Se guardará como borrador");
            write("[data-review-result]", value
                ? (unavailable ? "El odontólogo elegido ya no está disponible. Seleccioná otro profesional o dejá el estudio sin asignar para guardarlo como borrador." : "Se asociará el estudio al odontólogo elegido y se intentará publicarlo si supera las verificaciones.")
                : "El estudio se guardará como borrador, sin odontólogo derivante. Todavía no estará disponible para consulta.");
            write("[data-review-destination]", value && name ? `Destinatario: ${name}` : "");
            write("[data-review-submit-label]", value ? (unavailable ? "Revisar y confirmar" : "Confirmar y publicar") : "Guardar como borrador");
        }
        function updatePatient() {
            const selection = patient?.querySelector("[data-selector-selection]").textContent || "";
            if (selection.startsWith("Seleccionado: ")) {
                const [name, ...detail] = selection.slice(14).split(" · ");
                write("[data-review-patient]", name);
                write("[data-review-patient-detail]", detail.join(" · "));
            } else if (selection.startsWith("Selección no disponible")) {
                write("[data-review-patient]", "Revisá el paciente asignado");
                write("[data-review-patient-detail]", "Elegí una ficha disponible antes de confirmar");
            } else if (!patient?.querySelector("[data-selector-value]").value) {
                write("[data-review-patient]", "Sin paciente asignado");
                write("[data-review-patient-detail]", "Seleccioná una ficha para continuar");
            }
        }
        function updateStudy() {
            const type = form.querySelector('[name="tipo"]');
            const date = form.querySelector('[name="fecha_estudio"]');
            if (type) write("[data-review-type]", type.value || "Tipo no identificado");
            if (date) {
                const parts = date.value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
                write("[data-review-date]", parts ? `${parts[3]}/${parts[2]}/${parts[1]}` : date.value || "Fecha no identificada");
            }
        }
        for (const [root, update] of [[dentist, updateAccess], [patient, updatePatient]]) {
            root?.querySelector("[data-selector-value]").addEventListener("change", update);
            const selection = root?.querySelector("[data-selector-selection]");
            if (selection) new MutationObserver(update).observe(selection, {childList: true, characterData: true, subtree: true});
        }
        const status = dentist?.querySelector("[data-selector-status]");
        const empty = dentist?.querySelector("[data-review-empty]");
        if (status && empty) new MutationObserver(() => {
            empty.hidden = !status.textContent.startsWith("0 resultados");
        }).observe(status, {childList: true});
        form.querySelector('[name="tipo"]')?.addEventListener("input", updateStudy);
        form.querySelector('[name="fecha_estudio"]')?.addEventListener("input", updateStudy);
        updateAccess(); updatePatient(); updateStudy();
    });
    const navigation = document.querySelector(".confirmation-nav");
    navigation?.addEventListener("keydown", event => {
        if (event.key === "Escape" && navigation.open) {
            navigation.open = false;
            navigation.querySelector("summary").focus();
        }
    });
});
