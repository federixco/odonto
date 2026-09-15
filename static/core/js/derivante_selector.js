"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const normalizar = texto => (texto || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLocaleLowerCase("es");

    document.querySelectorAll("[data-derivante-selector]").forEach(selector => {
        const buscador = selector.querySelector("[data-derivante-search]");
        const filtroEstado = selector.querySelector("[data-derivante-status]");
        const tarjetas = Array.from(selector.querySelectorAll("[data-derivante-card]"));
        const contador = selector.querySelector("[data-derivante-count]");
        const vacio = selector.querySelector("[data-derivante-empty]");

        if (!tarjetas.length) return;

        function actualizarSeleccion() {
            tarjetas.forEach(tarjeta => {
                const radio = tarjeta.querySelector("input[type=radio]");
                tarjeta.classList.toggle("is-selected", Boolean(radio?.checked));
            });
        }

        function filtrar() {
            const consulta = normalizar(buscador?.value);
            const estado = filtroEstado?.value || "";
            let visibles = 0;

            tarjetas.forEach(tarjeta => {
                const coincideTexto = normalizar(tarjeta.dataset.search).includes(consulta);
                const coincideEstado = !estado || tarjeta.dataset.status === estado;
                const visible = coincideTexto && coincideEstado;
                tarjeta.hidden = !visible;
                if (visible) visibles += 1;
            });

            if (contador) contador.textContent = String(visibles);
            if (vacio) vacio.hidden = visibles !== 0;
        }

        buscador?.addEventListener("input", filtrar);
        filtroEstado?.addEventListener("change", filtrar);
        tarjetas.forEach(tarjeta => {
            tarjeta.querySelector("input[type=radio]")?.addEventListener("change", actualizarSeleccion);
        });

        actualizarSeleccion();
        filtrar();
    });
});
