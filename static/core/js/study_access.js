"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-study-access]");
    if (!root) return;
    const search = root.querySelector("[data-access-search]"), results = root.querySelector("[data-access-results]");
    const status = root.querySelector("[data-access-status-message]");
    const prev = root.querySelector("[data-access-prev]"), next = root.querySelector("[data-access-next]");
    const csrf = document.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    let page = 1, timer, controller, generation = 0;
    async function cargar() {
        controller?.abort(); controller = new AbortController(); const ticket = ++generation;
        prev.disabled = next.disabled = true; status.textContent = "Buscando…";
        const url = new URL(root.dataset.selectorUrl, location.origin);
        url.search = new URLSearchParams({q:search.value, page:String(page), estudio:root.dataset.estudioId});
        try {
            const response = await fetch(url, {signal:controller.signal});
            if (!response.ok) throw new Error("No se pudo buscar. Reintentá.");
            const data = await response.json(); if (ticket !== generation) return;
            results.replaceChildren();
            data.resultados.forEach(item => {
                const row = document.createElement("article"); row.className = "available-access-row";
                const identity = document.createElement("span"); identity.className = "access-identity";
                const title = document.createElement("strong"), detail = document.createElement("small");
                title.textContent = item.nombre; detail.textContent = item.detalle; identity.append(title, detail);
                const form = document.createElement("form"); form.method = "post";
                form.action = `/estudios/${root.dataset.estudioId}/accesos/agregar/`;
                for (const [name,value] of [["csrfmiddlewaretoken",csrf], ["odontologo",item.id]]) {
                    const input = document.createElement("input"); input.type = "hidden"; input.name = name; input.value = value;
                    form.append(input);
                }
                const button = document.createElement("button"); button.type = "submit"; button.className = "button button-small";
                button.textContent = "Dar acceso / reactivar"; form.append(button); row.append(identity,form); results.append(row);
            });
            page = data.pagina; status.textContent = `${data.total} disponibles · página ${page} de ${data.paginas}`;
            prev.disabled = !data.anterior; next.disabled = !data.siguiente;
        } catch(error) {if (error.name !== "AbortError" && ticket === generation) status.textContent = error.message;}
    }
    search.addEventListener("input", () => {controller?.abort(); generation += 1; clearTimeout(timer); page = 1; timer = setTimeout(cargar,250);});
    prev.addEventListener("click", () => {page -= 1; cargar();}); next.addEventListener("click", () => {page += 1; cargar();});
    cargar();
});
