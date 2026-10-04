"use strict";
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-selector-url]").forEach(root => {
        if (!root.querySelector("[data-selector-value]")) return;
        const value = root.querySelector("[data-selector-value]"), search = root.querySelector("[data-selector-search]");
        const results = root.querySelector("[data-selector-results]"), status = root.querySelector("[data-selector-status]");
        const selection = root.querySelector("[data-selector-selection]");
        const prev = root.querySelector("[data-selector-prev]"), next = root.querySelector("[data-selector-next]");
        let page = 1, timer, controller, serial = 0;
        root.seleccionarPaciente = elegir;
        function elegir(item) {
            value.value = item ? String(item.id) : "";
            selection.textContent = item ? `Seleccionado: ${item.nombre} · ${item.detalle}` : "Sin selección";
            results.querySelectorAll("[data-selector-id]").forEach(card => {
                const selected = card.dataset.selectorId === value.value;
                card.classList.toggle("is-selected", selected);
                card.querySelector("input").checked = selected;
            });
            value.dispatchEvent(new Event("change", {bubbles:true}));
        }
        async function cargar() {
            controller?.abort(); controller = new AbortController();
            const ticket = ++serial;
            status.textContent = "Buscando…"; prev.disabled = next.disabled = true;
            const url = new URL(root.dataset.selectorUrl, location.origin);
            url.search = new URLSearchParams({q:search.value, page:String(page), seleccionado:value.value});
            try {
                const response = await fetch(url, {signal:controller.signal, headers:{Accept:"application/json"}});
                if (!response.ok) throw new Error("No se pudo buscar. Reintentá la búsqueda.");
                const data = await response.json();
                if (ticket !== serial) return;
                results.replaceChildren();
                if (data.seleccionado) elegir(data.seleccionado);
                else selection.textContent = value.value ? "Selección no disponible: elegí otra opción." : "Sin selección";
                data.resultados.forEach(item => {
                    const card = document.createElement("label"); card.className = "derivante-option";
                    card.dataset.selectorId = String(item.id);
                    const radio = document.createElement("input"); radio.type = "radio";
                    radio.name = `selector_${value.name}`; radio.value = String(item.id);
                    radio.checked = value.value === String(item.id); card.classList.toggle("is-selected", radio.checked);
                    radio.addEventListener("change", () => elegir(item));
                    const identity = document.createElement("span"); identity.className = "derivante-identity";
                    const title = document.createElement("strong"), detail = document.createElement("small");
                    title.textContent = item.nombre; detail.textContent = item.detalle;
                    identity.append(title, detail); card.append(radio, identity); results.append(card);
                });
                page = data.pagina; status.textContent = `${data.total} resultados · página ${page} de ${data.paginas}`;
                prev.disabled = !data.anterior; next.disabled = !data.siguiente;
            } catch (error) {
                if (error.name !== "AbortError" && ticket === serial) status.textContent = error.message;
            }
        }
        search.addEventListener("input", () => {
            controller?.abort(); serial += 1; clearTimeout(timer); page = 1; timer = setTimeout(cargar, 250);
        });
        prev.addEventListener("click", () => {page -= 1; cargar();});
        next.addEventListener("click", () => {page += 1; cargar();});
        root.querySelector("[data-selector-clear]")?.addEventListener("click", () => elegir(null));
        cargar();
    });
});
