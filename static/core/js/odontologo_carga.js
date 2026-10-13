"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector(".dentist-directory-page [data-importacion-uploader]");
    if (!root?.docImportacion) return;
    const rows = [...document.querySelectorAll("[data-dentist-target]")];
    const explorer = document.querySelector("#explorer-container");
    const viewButton = document.querySelector("#view-mode-btn");
    const viewMenu = document.querySelector("#view-mode-menu");
    if (explorer && viewButton && viewMenu) {
        viewButton.hidden = false;
        const syncView = () => {
            viewMenu.querySelectorAll(".view-option").forEach(option => {
                const active = explorer.classList.contains(option.dataset.view);
                option.setAttribute("aria-pressed", String(active));
                if (active) viewButton.querySelector("[data-view-label]").textContent = `Ver: ${option.textContent}`;
            });
        };
        syncView();
        new MutationObserver(syncView).observe(explorer, {attributes: true, attributeFilter: ["class"]});
        viewMenu.addEventListener("click", event => {if (event.target.closest(".view-option")) viewButton.focus();});
        document.addEventListener("keydown", event => {
            if (event.key === "Escape" && !viewMenu.hidden) {
                viewMenu.hidden = true; viewButton.setAttribute("aria-expanded", "false"); viewButton.focus();
            }
        });
    }
    const message = document.querySelector("[data-drop-message]");
    const title = root.querySelector("#upload-recipient");
    const summary = root.querySelector("[data-file-summary]");
    const errorBox = root.querySelector("#upload-error");
    const start = root.querySelector("[data-upload-start]");
    const cancel = root.querySelector("[data-selection-cancel]");
    const folder = root.querySelector("#dentist-folder-input");
    const filesInput = root.querySelector("#dentist-files-input");
    let recipient = null, files = [], reading = false, version = 0;
    const occupied = () => reading || root.docImportacion.ocupada;
    const announce = text => {message.textContent = text; message.hidden = !text;};
    const clearDrag = () => {document.body.classList.remove("is-file-drag"); rows.forEach(row => row.classList.remove("is-drop-target"));};
    const fileDrag = event => [...(event.dataTransfer?.types || [])].includes("Files");
    const error = text => {errorBox.textContent = text; errorBox.hidden = false;};
    function controls() {
        const locked = occupied();
        rows.forEach(row => {row.querySelector("[data-select-dentist]").disabled = locked;});
        root.querySelectorAll("[data-pick-folder], [data-pick-files]").forEach(button => {button.disabled = locked;});
        start.disabled = locked || !files.length;
        cancel.hidden = root.docImportacion.ocupada;
        root.querySelector("[data-preparation-actions]").hidden = root.docImportacion.ocupada;
        if (summary.dataset.original) summary.textContent = summary.dataset.original + (root.dataset.busy === "true" ? " Envío en curso." : root.docImportacion.ocupada ? " Carga pendiente. Podés reintentar o cancelar." : " Todavía no se envió el estudio.");
    }
    function select(row) {
        if (occupied()) return false;
        version += 1; files = []; delete summary.dataset.original; announce("");
        recipient = {id: row.dataset.dentistId, name: row.dataset.dentistName, license: row.dataset.dentistLicense};
        rows.forEach(item => item.classList.toggle("is-recipient", item.dataset.dentistId === recipient.id));
        title.textContent = `Cargar estudio para ${recipient.name}`;
        root.querySelector("[data-upload-license]").textContent = `Matrícula ${recipient.license}`;
        summary.textContent = "Elegí la carpeta original o los archivos del estudio.";
        errorBox.hidden = true; root.querySelector("#upload-progress-container").hidden = true;
        folder.value = filesInput.value = ""; root.hidden = false; controls();
        return true;
    }
    function focusPreparation() {root.scrollIntoView({block: "start", behavior: "instant"}); title.focus({preventScroll: true});}
    function prepare(selected) {
        files = Array.from(selected);
        const bytes = files.reduce((sum, file) => sum + file.size, 0);
        const unit = bytes < 1024 ? "bytes" : bytes < 1024 * 1024 ? "KB" : "MB";
        const size = new Intl.NumberFormat("es-AR", {maximumFractionDigits: 1}).format(bytes / (unit === "bytes" ? 1 : unit === "KB" ? 1024 : 1024 * 1024));
        const path = files[0]?._docRelativePath || files[0]?.webkitRelativePath || files[0]?.name;
        const name = path?.split("/")[0] || "Sin archivos seleccionados";
        summary.dataset.original = `${name} · ${files.length} archivo${files.length === 1 ? "" : "s"} · ${size} ${unit}.`;
        errorBox.hidden = true; controls(); focusPreparation();
    }
    rows.forEach(row => {
        const button = row.querySelector("[data-select-dentist]"); button.hidden = false;
        button.addEventListener("click", () => {if (select(row)) focusPreparation();});
        row.addEventListener("dragover", event => {
            if (!fileDrag(event)) return;
            event.preventDefault();
            if (occupied()) {event.dataTransfer.dropEffect = "none"; return;}
            event.dataTransfer.dropEffect = "copy";
            rows.forEach(item => item.classList.toggle("is-drop-target", item === row));
            announce(`Soltar para ${row.dataset.dentistName} · ${row.dataset.dentistLicense}`);
        });
        row.addEventListener("dragleave", event => {if (!row.contains(event.relatedTarget)) row.classList.remove("is-drop-target");});
        row.addEventListener("drop", async event => {
            if (!fileDrag(event)) return;
            event.preventDefault(); event.stopPropagation(); clearDrag(); announce("");
            // Capturar referencias mientras DataTransfer sigue disponible.
            const entries = [...(event.dataTransfer.items || [])].map(item => item.webkitGetAsEntry?.()).filter(Boolean);
            const fallback = Array.from(event.dataTransfer.files || []);
            if (!select(row)) {announce("Esperá o cancelá la carga actual antes de elegir otro derivante."); return;}
            const ticket = version;
            reading = true; controls(); summary.textContent = "Leyendo los archivos seleccionados…"; focusPreparation();
            try {
                const directories = entries.filter(entry => entry.isDirectory);
                if (directories.length && (entries.length !== 1 || directories.length !== 1)) throw new Error("Soltá una carpeta por estudio. También podés seleccionar archivos sueltos.");
                const selected = entries.length ? (await Promise.all(entries.map(entry => root.docImportacion.leerEntrada(entry)))).flat() : fallback;
                if (ticket !== version) return;
                reading = false; prepare(selected);
            } catch (failure) {if (ticket === version) {reading = false; error(failure.message || "No pudimos leer los archivos. Elegilos manualmente.");}}
            finally {if (ticket === version) {reading = false; controls();}}
        });
    });
    root.querySelector("[data-pick-folder]").addEventListener("click", () => folder.click());
    root.querySelector("[data-pick-files]").addEventListener("click", () => filesInput.click());
    [folder, filesInput].forEach(input => input.addEventListener("change", () => {if (!occupied()) prepare(input.files);}));
    cancel.addEventListener("click", () => {
        if (root.docImportacion.ocupada) return;
        version += 1; reading = false; files = []; root.hidden = true;
        rows.forEach(row => row.classList.remove("is-recipient"));
        rows.find(row => row.dataset.dentistId === recipient?.id && row.getClientRects().length)?.querySelector("[data-select-dentist]")?.focus();
        recipient = null; controls();
    });
    start.addEventListener("click", async () => {
        if (!recipient || !files.length || occupied()) return;
        window.DOC_UPLOAD_REDIRECT_APPEND = `?derivante=${encodeURIComponent(recipient.id)}&origen=odontologos`;
        await root.docImportacion.cargar(files);
        controls();
    });
    new MutationObserver(controls).observe(root, {attributes: true, attributeFilter: ["data-busy"]});
    document.addEventListener("dragover", event => {
        if (!fileDrag(event)) return;
        event.preventDefault();
        if (occupied()) {event.dataTransfer.dropEffect = "none"; return;}
        document.body.classList.add("is-file-drag");
        if (!event.target.closest("[data-dentist-target]")) {event.dataTransfer.dropEffect = "none"; rows.forEach(row => row.classList.remove("is-drop-target")); announce("Soltá sobre un odontólogo habilitado para preparar la carga.");}
    });
    document.addEventListener("dragleave", event => {if (!event.relatedTarget) {clearDrag(); announce("");}});
    document.addEventListener("dragend", () => {clearDrag(); announce("");});
    document.addEventListener("drop", event => {if (fileDrag(event)) {event.preventDefault(); clearDrag(); announce(occupied() ? "Esperá o cancelá la carga actual antes de elegir otro derivante." : "El archivo no se cargó. Soltalo sobre un odontólogo habilitado.");}});
});
