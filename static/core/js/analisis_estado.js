"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-analisis-lote]");
    if (!root) return;
    const base = `/estudios/importaciones/${root.dataset.analisisLote}/`;
    const text = root.querySelector("[data-analisis-mensaje]");
    const csrf = root.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    let timer;
    async function revisar() {
        if (document.hidden) {timer = setTimeout(revisar, 5000); return;}
        try {
            const response = await fetch(base + "estado/", {signal:AbortSignal.timeout(15000)});
            if (!response.ok) throw new Error();
            const data = await response.json();
            if (data.estado === "PENDIENTE_CONFIRMACION" || data.estado === "CONFIRMADA") {location.reload(); return;}
            if (data.estado === "ERROR" || data.estado === "CANCELADA") {location.reload(); return;}
            const fase = data.fase === "verificacion" ? "Verificando archivos" : "Analizando metadatos";
            text.textContent = data.trabajo === "pendiente" ? "Esperando al trabajador de análisis. Si no avanza, iniciá el worker." : `${fase}: ${data.procesados} de ${data.total}.`;
        } catch (_) {text.textContent = "No pudimos consultar el estado. Reintentando…";}
        timer = setTimeout(revisar, 3000);
    }
    root.querySelector("[data-analisis-reintentar]")?.addEventListener("click", () => operar("analizar"));
    root.querySelector("[data-analisis-cancelar]")?.addEventListener("click", () => {
        if (confirm("¿Cancelar esta carpeta y descartar los archivos subidos?")) operar("cancelar");
    });
    async function operar(accion) {
        root.querySelectorAll("button").forEach(b => b.disabled = true);
        try {
            const response = await fetch(base + accion + "/", {method:"POST", headers:{"X-CSRFToken":csrf}, signal:AbortSignal.timeout(15000)});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            location.reload();
        } catch (error) {text.textContent = error.message; root.querySelectorAll("button").forEach(b => b.disabled = false);}
    }
    if (root.dataset.estado === "PROCESANDO") revisar();
    window.addEventListener("pagehide", () => clearTimeout(timer), {once:true});
});
