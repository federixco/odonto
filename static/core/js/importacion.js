"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-importacion-uploader]");
    if (!root) return;

    const input = document.getElementById("folder-input");
    const button = document.getElementById("folder-select-button");
    const dropZone = document.getElementById("drop-zone");
    const progress = document.getElementById("upload-progress-container");
    const progressBar = document.getElementById("progress-bar");
    const progressTrack = document.querySelector(".progress-bar-wrap");
    const progressText = document.getElementById("progress-text");
    const progressTitle = document.getElementById("progress-title");
    const errorBox = document.getElementById("upload-error");
    const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
    const stages = {
        upload: document.getElementById("stage-upload"),
        analyze: document.getElementById("stage-analyze"),
        review: document.getElementById("stage-review"),
    };
    const reintentos = 3;

    const mostrarError = (mensaje) => {
        errorBox.textContent = mensaje;
        errorBox.hidden = false;
    };

    function activarEtapa(nombre) {
        const orden = ["upload", "analyze", "review"];
        const indice = orden.indexOf(nombre);
        orden.forEach((etapa, posicion) => {
            stages[etapa]?.classList.toggle("is-active", posicion === indice);
            stages[etapa]?.classList.toggle("is-complete", posicion < indice);
        });
    }

    async function respuestaError(respuesta, alternativa) {
        try {
            return (await respuesta.json()).error || alternativa;
        } catch (_) {
            return alternativa;
        }
    }

    async function jsonPost(url, body) {
        const respuesta = await fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
            body: JSON.stringify(body),
        });
        if (!respuesta.ok) {
            throw new Error(await respuestaError(respuesta, "No se pudo continuar."));
        }
        return respuesta.json();
    }

    function subirParte(url, bloque, informar) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("PUT", url, true);
            xhr.upload.onprogress = (evento) => {
                if (evento.lengthComputable) informar(evento.loaded);
            };
            xhr.onload = () => {
                const etag = xhr.getResponseHeader("ETag");
                if (xhr.status >= 200 && xhr.status < 300 && etag) resolve(etag);
                else reject(new Error("El almacenamiento no confirmó una parte."));
            };
            xhr.onerror = () => reject(new Error("Se interrumpió la conexión con el almacenamiento."));
            xhr.send(bloque);
        });
    }

    async function subirArchivo(loteId, archivo, informar) {
        const ruta = archivo._docRelativePath || archivo.webkitRelativePath || archivo.name;
        const inicio = await jsonPost(`/estudios/importaciones/${loteId}/archivos/iniciar/`, {
            ruta_relativa: ruta,
            tamano: archivo.size,
        });
        const partes = [];
        for (const parte of inicio.partes) {
            const desde = (parte.part_number - 1) * inicio.part_size;
            const hasta = Math.min(desde + inicio.part_size, archivo.size);
            let etag;
            for (let intento = 1; intento <= reintentos && !etag; intento += 1) {
                try {
                    etag = await subirParte(
                        parte.url,
                        archivo.slice(desde, hasta),
                        bytes => informar(Math.min(desde + bytes, archivo.size)),
                    );
                } catch (error) {
                    if (intento === reintentos) throw error;
                }
            }
            partes.push({PartNumber: parte.part_number, ETag: etag});
            informar(hasta);
        }
        await jsonPost(
            `/estudios/importaciones/${loteId}/archivos/${inicio.archivo_id}/completar/`,
            {partes},
        );
    }

    function leerArchivo(entry, ruta) {
        return new Promise((resolve, reject) => {
            entry.file(file => {
                Object.defineProperty(file, "_docRelativePath", {
                    value: `${ruta}${entry.name}`,
                    configurable: true,
                });
                resolve([file]);
            }, reject);
        });
    }

    function leerLote(reader) {
        return new Promise((resolve, reject) => reader.readEntries(resolve, reject));
    }

    async function recorrerEntrada(entry, ruta = "") {
        if (entry.isFile) return leerArchivo(entry, ruta);
        if (!entry.isDirectory) return [];

        const reader = entry.createReader();
        const entradas = [];
        let lote;
        do {
            lote = await leerLote(reader);
            entradas.push(...lote);
        } while (lote.length);

        const resultados = await Promise.all(
            entradas.map(hija => recorrerEntrada(hija, `${ruta}${entry.name}/`)),
        );
        return resultados.flat();
    }

    async function archivosDesdeCarpetaSoltada(transferencia) {
        const entradas = Array.from(transferencia.items || [])
            .map(item => item.webkitGetAsEntry?.())
            .filter(Boolean);
        if (entradas.length !== 1 || !entradas[0].isDirectory) {
            throw new Error("Arrastrá una sola carpeta completa, no archivos sueltos.");
        }
        return recorrerEntrada(entradas[0]);
    }

    async function procesar(filesEntrada) {
        if (root.dataset.busy === "true") return;
        const files = Array.from(filesEntrada).filter(file => file.size > 0);
        if (!files.length) {
            mostrarError("Seleccioná una carpeta que contenga al menos un archivo.");
            return;
        }

        root.dataset.busy = "true";
        button.disabled = input.disabled = true;
        errorBox.hidden = true;
        progress.hidden = false;
        activarEtapa("upload");
        const total = files.reduce((suma, archivo) => suma + archivo.size, 0);
        const primeraRuta = files[0]._docRelativePath || files[0].webkitRelativePath || "Estudio";
        const carpeta = primeraRuta.split("/")[0] || "Estudio";

        try {
            const lote = await jsonPost("/estudios/importaciones/iniciar/", {
                nombre_carpeta: carpeta,
                cantidad_archivos: files.length,
                tamano_total: total,
            });
            let acumulado = 0;
            for (let indice = 0; indice < files.length; indice += 1) {
                const archivo = files[indice];
                progressText.textContent = `${indice + 1} de ${files.length}: ${archivo.name}`;
                await subirArchivo(lote.importacion_id, archivo, bytes => {
                    const porcentaje = Math.round(((acumulado + bytes) / total) * 100);
                    progressBar.style.width = `${porcentaje}%`;
                    progressTrack.setAttribute("aria-valuenow", String(porcentaje));
                });
                acumulado += archivo.size;
            }

            activarEtapa("analyze");
            progressTitle.textContent = "Detectando datos del paciente";
            progressText.textContent = "Leyendo la información de la carpeta…";
            const analisis = await jsonPost(`/estudios/importaciones/${lote.importacion_id}/analizar/`, {});
            progressBar.style.width = "100%";
            progressTrack.setAttribute("aria-valuenow", "100");
            activarEtapa("review");
            progressTitle.textContent = "Datos encontrados";
            progressText.textContent = "Abriendo confirmación…";
            window.location.assign(analisis.detalle_url + (window.DOC_UPLOAD_REDIRECT_APPEND || ""));
        } catch (error) {
            mostrarError(error.message || "No se pudo importar la carpeta.");
            progress.hidden = true;
            button.disabled = input.disabled = false;
            input.value = "";
            root.dataset.busy = "false";
        }
    }

    button.addEventListener("click", () => input.click());
    input.addEventListener("change", evento => procesar(evento.target.files));

    ["dragenter", "dragover"].forEach(nombre => {
        dropZone.addEventListener(nombre, evento => {
            evento.preventDefault();
            if (root.dataset.busy !== "true") dropZone.classList.add("is-dragging");
        });
    });
    ["dragleave", "dragend"].forEach(nombre => {
        dropZone.addEventListener(nombre, () => dropZone.classList.remove("is-dragging"));
    });
    dropZone.addEventListener("drop", async evento => {
        evento.preventDefault();
        dropZone.classList.remove("is-dragging");
        try {
            const files = await archivosDesdeCarpetaSoltada(evento.dataTransfer);
            await procesar(files);
        } catch (error) {
            mostrarError(error.message || "No pudimos leer la carpeta.");
        }
    });

    window.DOC_manejarDropOdontologo = async function(e, nombreOdontologo, idOdontologo) {
        e.preventDefault();
        e.stopPropagation();
        
        // Remove styling class
        e.currentTarget.style.borderColor = "";
        e.currentTarget.style.backgroundColor = "";

        if (root.dataset.busy === "true") return;
        
        if (!window.confirm("¿Estás seguro que deseas cargar y asignar esta carpeta de estudio para " + nombreOdontologo + "?")) {
            return;
        }

        window.DOC_UPLOAD_REDIRECT_APPEND = "?derivante=" + idOdontologo;
        
        if (root.tagName === "DIALOG") {
            root.showModal();
        } else {
            root.hidden = false;
        }
        
        try {
            const files = await archivosDesdeCarpetaSoltada(e.dataTransfer);
            await procesar(files);
        } catch (err) {
            mostrarError(err.message);
        }
    };
});
