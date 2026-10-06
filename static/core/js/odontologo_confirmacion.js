"use strict";
// Presentación exclusiva de importaciones iniciadas desde el directorio.
(() => {
    const script = document.currentScript;
    const importation = location.pathname.match(/\/importaciones\/(\d+)(?:\/(?:confirmar|registrar-paciente))?\/?$/)?.[1];
    if (!importation || !script?.dataset.adminId) return;
    const key = `doc:derivante:${script.dataset.adminId}:${importation}`;
    const query = new URLSearchParams(location.search);
    const save = id => {try {sessionStorage.setItem(key, id);} catch (_) { /* El formulario conserva su selección. */ }};
    let selected = null;
    try {selected = sessionStorage.getItem(key);} catch (_) { /* Sin persistencia entre pantallas. */ }
    if (query.get("origen") === "odontologos" && /^\d+$/.test(query.get("derivante") || "")) {
        selected = query.get("derivante"); save(selected);
    }
    if (selected === null) return;
    const failed = !!document.querySelector("[data-review-form] .confirmation-error");
    document.querySelectorAll("[data-derivante-selector] [data-selector-value]").forEach(input => {
        if (!failed) input.value = selected;
        else {selected = input.value; save(selected);}
    });
    document.body.classList.add("derivante-review");
    const style = document.createElement("link"); style.rel = "stylesheet"; style.href = script.dataset.styleUrl; document.head.append(style);
    const breadcrumb = document.querySelector(".confirmation-breadcrumb a");
    if (breadcrumb) {breadcrumb.href = script.dataset.directoryUrl; breadcrumb.textContent = "Odontólogos derivantes";}
    document.addEventListener("DOMContentLoaded", () => {
        const work = document.querySelector(".confirmation-work");
        const context = document.createElement("div"); context.className = "derivante-context"; context.setAttribute("role", "status");
        const label = document.createElement("strong"); label.textContent = "Odontólogo derivante: ";
        const value = document.createElement("span"); value.textContent = selected ? "Verificando selección…" : "Sin asignar. Se guardará como borrador.";
        context.append(label, value); work.querySelector(".confirmation-source").after(context);
        const selectors = [...document.querySelectorAll("[data-derivante-selector]")];
        selectors.forEach(root => {
            const input = root.querySelector("[data-selector-value]");
            const selection = root.querySelector("[data-selector-selection]");
            const details = document.createElement("details"); details.className = "derivante-change";
            const summary = document.createElement("summary"); summary.textContent = "Cambiar odontólogo o acceso"; details.append(summary);
            const heading = root.querySelector(".confirmation-section-heading");
            [...root.children].filter(node => node !== heading && node !== input && node !== selection).forEach(node => details.append(node));
            root.append(details);
            function update() {
                const verified = selection.textContent.startsWith("Seleccionado:");
                value.textContent = verified ? selection.textContent.replace(/^Seleccionado:\s*/, "") : input.value ? "Selección pendiente de verificar. Revisá el odontólogo antes de confirmar." : "Sin asignar. Se guardará como borrador.";
                if (!verified || root.querySelector(".field-error")) details.open = true;
                else if (!details.dataset.interacted) details.open = false;
            }
            summary.addEventListener("click", () => {details.dataset.interacted = "true";});
            input.addEventListener("change", () => {selected = input.value; save(selected); update();});
            new MutationObserver(update).observe(selection, {childList: true, characterData: true, subtree: true});
            update();
        });
        // Durante el análisis o la identificación aún no hay selector visible.
        if (!selectors.length && selected) {
            const url = new URL(script.dataset.selectorUrl, location.origin); url.searchParams.set("seleccionado", selected);
            fetch(url, {headers: {Accept: "application/json"}}).then(response => {
                if (!response.ok) throw new Error("No se pudo verificar el derivante."); return response.json();
            }).then(data => {value.textContent = data.seleccionado ? `${data.seleccionado.nombre} · ${data.seleccionado.detalle}` : "Selección no disponible. Deberás elegir un odontólogo habilitado antes de publicar.";}).catch(() => {value.textContent = "No se pudo verificar la selección. Podrás revisarla antes de confirmar.";});
        }
        document.querySelectorAll("form.confirmation-document[data-review-form]").forEach(form => {
            const fields = ["tipo", "fecha_estudio"].map(name => form.querySelector(`[name="${name}"]`)).filter(input => input && !input.value);
            if (!fields.length) return;
            const section = document.createElement("div"); section.className = "confirmation-missing admin-form";
            const heading = document.createElement("h3"); heading.textContent = "Completá los datos faltantes"; section.append(heading);
            fields.forEach(input => section.append(input.closest(".form-field")));
            form.querySelector(".confirmation-data .confirmation-correction").before(section);
        });
        const patientForm = document.querySelector("#compact-patient-form");
        if (patientForm) {
            const names = ["nombre", "apellido", "dni"].map(name => patientForm.querySelector(`[name="${name}"]`));
            const detected = names.filter(input => input?.value.trim() && !input.closest(".form-field").querySelector(".errorlist"));
            if (detected.length) {
                const summary = document.createElement("div"); summary.className = "detected-patient-summary";
                const name = document.createElement("strong"); name.textContent = [names[0]?.value, names[1]?.value].filter(Boolean).join(" ");
                const dni = document.createElement("small"); dni.textContent = names[2]?.value ? `DNI ${names[2].value}` : "DNI pendiente de completar"; summary.append(name, dni);
                patientForm.querySelector(".form-grid").before(summary);
                const details = document.createElement("details"); details.className = "confirmation-correction";
                const title = document.createElement("summary"); title.textContent = "Revisar datos detectados";
                const grid = document.createElement("div"); grid.className = "form-grid confirmation-correction-body"; details.append(title, grid);
                detected.forEach(input => grid.append(input.closest(".form-field"))); summary.after(details);
                if (detected.length === 3) patientForm.querySelector(".form-grid:not(.confirmation-correction-body)")?.remove();
            }
        }
    });
})();
