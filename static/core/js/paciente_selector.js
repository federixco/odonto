"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("compact-patient-form"), dni = form?.querySelector('[name="dni"]');
    const root = document.querySelector("[data-paciente-selector]");
    if (!dni || !root) return;
    const dialog = document.getElementById("dni-confirm-dialog"), text = document.getElementById("dni-confirm-text");
    let match = null, consultado = "", controller, ticket = 0;
    function asignar() {
        if (!match || dni.value.trim() !== consultado) return;
        root.seleccionarPaciente?.(match);
        if (dialog?.open) dialog.close();
        root.closest("form")?.requestSubmit();
    }
    async function buscar() {
        controller?.abort(); controller = new AbortController();
        const serie = ++ticket, valor = dni.value.trim();
        if (!valor) return false;
        const url = new URL(root.dataset.selectorUrl, location.origin); url.searchParams.set("dni", valor);
        const response = await fetch(url, {signal:controller.signal});
        if (!response.ok) throw new Error("No se pudo verificar el DNI. Volvé a intentar.");
        const data = await response.json();
        if (serie !== ticket || dni.value.trim() !== valor) return true;
        match = data.resultados[0] || null; consultado = valor;
        if (!match) return false;
        const mensaje = `Ya existe ${match.nombre} con DNI ${valor}. ¿Asociar el estudio a su ficha existente?`;
        if (text) text.textContent = mensaje;
        if (dialog?.showModal) {if (!dialog.open) dialog.showModal();}
        else if (window.confirm(mensaje)) asignar();
        return true;
    }
    document.getElementById("dni-confirm-accept")?.addEventListener("click", asignar);
    document.getElementById("dni-confirm-cancel")?.addEventListener("click", () => {match = null; dialog?.close();});
    dni.addEventListener("input", () => {controller?.abort(); ticket += 1; match = null; consultado = "";});
    dni.addEventListener("blur", () => buscar().catch(() => {}));
    let verificado = false;
    form.addEventListener("submit", async event => {
        if (verificado) return;
        event.preventDefault();
        try {
            const valor = dni.value.trim();
            if (!(await buscar()) && dni.value.trim() === valor) {
                verificado = true; form.requestSubmit(); verificado = false;
            }
        } catch (error) {if (error.name !== "AbortError") window.alert(error.message);}
    });
});
