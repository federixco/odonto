"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-importacion-uploader]");
    if (!root) return;
    const input = document.getElementById("folder-input");
    const button = document.getElementById("folder-select-button");
    const progress = document.getElementById("upload-progress-container");
    const progressBar = document.getElementById("progress-bar");
    const progressTrack = document.querySelector(".progress-bar-wrap");
    const progressText = document.getElementById("progress-text");
    const errorBox = document.getElementById("upload-error");
    const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
    const reintentos = 3;

    const mostrarError = (mensaje) => { errorBox.textContent = mensaje; errorBox.hidden = false; };
    async function respuestaError(respuesta, alternativa) { try { return (await respuesta.json()).error || alternativa; } catch (_) { return alternativa; } }
    async function jsonPost(url, body) {
        const respuesta = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json", "X-CSRFToken": csrf}, body: JSON.stringify(body)});
        if (!respuesta.ok) throw new Error(await respuestaError(respuesta, "No se pudo continuar."));
        return respuesta.json();
    }
    function subirParte(url, bloque, informar) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest(); xhr.open("PUT", url, true);
            xhr.upload.onprogress = (evento) => { if (evento.lengthComputable) informar(evento.loaded); };
            xhr.onload = () => xhr.status >= 200 && xhr.status < 300 && xhr.getResponseHeader("ETag") ? resolve(xhr.getResponseHeader("ETag")) : reject(new Error("El almacenamiento no confirmó una parte."));
            xhr.onerror = () => reject(new Error("Se interrumpió la conexión con el almacenamiento.")); xhr.send(bloque);
        });
    }
    async function subirArchivo(loteId, archivo, informar) {
        const ruta = archivo.webkitRelativePath || archivo.name;
        const inicio = await jsonPost(`/estudios/importaciones/${loteId}/archivos/iniciar/`, {ruta_relativa: ruta, tamano: archivo.size});
        const partes = [];
        for (const parte of inicio.partes) {
            const desde = (parte.part_number - 1) * inicio.part_size;
            const hasta = Math.min(desde + inicio.part_size, archivo.size);
            let etag;
            for (let intento = 1; intento <= reintentos && !etag; intento += 1) {
                try { etag = await subirParte(parte.url, archivo.slice(desde, hasta), bytes => informar(Math.min(desde + bytes, archivo.size))); }
                catch (error) { if (intento === reintentos) throw error; }
            }
            partes.push({PartNumber: parte.part_number, ETag: etag}); informar(hasta);
        }
        await jsonPost(`/estudios/importaciones/${loteId}/archivos/${inicio.archivo_id}/completar/`, {partes});
    }
    async function procesar(filesEntrada) {
        const files = Array.from(filesEntrada).filter(file => file.size > 0);
        if (!files.length) return mostrarError("Seleccioná una carpeta que contenga al menos un archivo.");
        button.disabled = input.disabled = true; errorBox.hidden = true; progress.hidden = false;
        const total = files.reduce((suma, archivo) => suma + archivo.size, 0);
        const carpeta = (files[0].webkitRelativePath || "Estudio").split("/")[0] || "Estudio";
        try {
            const lote = await jsonPost("/estudios/importaciones/iniciar/", {nombre_carpeta: carpeta, cantidad_archivos: files.length, tamano_total: total});
            let acumulado = 0;
            for (let indice = 0; indice < files.length; indice += 1) {
                const archivo = files[indice];
                progressText.textContent = `Subiendo ${indice + 1} de ${files.length}: ${archivo.name}`;
                await subirArchivo(lote.importacion_id, archivo, bytes => {
                    const porcentaje = Math.round(((acumulado + bytes) / total) * 100);
                    progressBar.style.width = `${porcentaje}%`; progressTrack.setAttribute("aria-valuenow", String(porcentaje));
                });
                acumulado += archivo.size;
            }
            progressText.textContent = "Analizando estructura y metadatos…";
            const analisis = await jsonPost(`/estudios/importaciones/${lote.importacion_id}/analizar/`, {});
            progressBar.style.width = "100%"; progressTrack.setAttribute("aria-valuenow", "100");
            window.location.assign(analisis.detalle_url);
        } catch (error) {
            mostrarError(error.message || "No se pudo importar la carpeta.");
            progress.hidden = true; button.disabled = input.disabled = false;
        }
    }
    button.addEventListener("click", () => input.click());
    input.addEventListener("change", evento => procesar(evento.target.files));
});
