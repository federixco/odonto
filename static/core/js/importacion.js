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
    let controller, pendiente = null, cancelando = false, leyendo = false;
    const controles = document.createElement("div");
    const cancelar = document.createElement("button"), reintentar = document.createElement("button");
    cancelar.type = reintentar.type = "button";
    cancelar.className = "button button-secondary"; reintentar.className = "button";
    cancelar.textContent = "Cancelar carga"; reintentar.textContent = "Reintentar carga";
    reintentar.hidden = true; controles.append(cancelar, reintentar); progress.append(controles);
    reintentar.addEventListener("click", () => {if (pendiente && !cancelando) procesar(pendiente.files);});
    cancelar.addEventListener("click", async () => {
        if (!pendiente || !confirm("¿Cancelar y descartar esta carpeta?")) return;
        cancelando = true; controller?.abort(); cancelar.disabled = reintentar.disabled = true;
        try {
            // Si se perdió la respuesta de inicio, recuperar el mismo lote por su UUID.
            const lote = pendiente.lote || await jsonPost("/estudios/importaciones/iniciar/", pendiente.datos, true);
            await jsonPost(`/estudios/importaciones/${lote.importacion_id}/cancelar/`, {}, true);
            pendiente = null; cancelando = false;
            progressText.textContent = "Importación cancelada. El worker limpiará sus archivos de MinIO.";
            cancelar.hidden = reintentar.hidden = true;
            button.disabled = input.disabled = false; input.value = "";
        } catch (error) {
            mostrarError("No se confirmó la cancelación. Volvé a pulsar Cancelar: " + error.message);
            cancelar.disabled = false;
        } finally {root.dataset.busy = "false";}
    });

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

    async function jsonPost(url, body, independiente = false) {
      const activo = controller;
      for (let intento = 0; intento < 3; intento += 1) {
        try {
        const signal = independiente ? AbortSignal.timeout(30000) : AbortSignal.any([activo.signal, AbortSignal.timeout(30000)]);
        const respuesta = await fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
            body: JSON.stringify(body),
            signal,
        });
        if (!respuesta.ok) {
            let data = {}; try {data = await respuesta.json();} catch (_) {}
            const error = new Error(data.error || "No se pudo continuar.");
            error.reintentable = respuesta.status >= 500 || respuesta.status === 429 || data.reintentable === true;
            throw error;
        }
        return await respuesta.json();
        } catch (error) {
            if ((!independiente && activo.signal.aborted) || error.name === "AbortError" || error.reintentable === false || intento === 2) throw error;
            await new Promise(resolve => setTimeout(resolve, 800 * (2 ** intento) + Math.random() * 250));
        }
      }
    }

    function subirParte(url, bloque, informar, signal) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("PUT", url, true);
            xhr.timeout = 120000;
            const abortar = () => xhr.abort();
            if (signal.aborted) {reject(new DOMException("Carga cancelada", "AbortError")); return;}
            signal.addEventListener("abort", abortar, {once:true});
            xhr.onloadend = () => signal.removeEventListener("abort", abortar);
            xhr.onabort = () => reject(new DOMException("Carga cancelada", "AbortError"));
            xhr.ontimeout = () => reject(new Error("La parte excedió el tiempo de espera."));
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
        const activo = controller;
        const ruta = archivo._docRelativePath || archivo.webkitRelativePath || archivo.name;
        const anterior = pendiente.archivos.get(ruta);
        if (anterior?.partes) {
            try {
                await jsonPost(`/estudios/importaciones/${loteId}/archivos/${anterior.inicio.archivo_id}/completar/`,
                    {partes:anterior.partes,carga_token:anterior.inicio.carga_token});
                informar(archivo.size); return;
            } catch(error) {
                if (activo.signal.aborted || error.reintentable !== false) throw error;
                pendiente.archivos.delete(ruta);
            }
        }
        const inicio = await jsonPost(`/estudios/importaciones/${loteId}/archivos/iniciar/`, {
            ruta_relativa: ruta,
            tamano: archivo.size,
        });
        if (inicio.status === "completo") {informar(archivo.size); return;}
        const partes = [];
        for (const parte of inicio.partes) {
            const desde = (parte.part_number - 1) * inicio.part_size;
            const hasta = Math.min(desde + inicio.part_size, archivo.size);
            let etag;
            for (let intento = 1; intento <= reintentos && !etag; intento += 1) {
                if (activo.signal.aborted) throw new DOMException("Carga cancelada", "AbortError");
                try {
                    etag = await subirParte(
                        parte.url,
                        archivo.slice(desde, hasta),
                        bytes => informar(Math.min(desde + bytes, archivo.size)),
                        activo.signal,
                    );
                } catch (error) {
                    if (activo.signal.aborted || intento === reintentos) throw error;
                    await new Promise(resolve => setTimeout(resolve, 800 * (2 ** (intento - 1))));
                }
            }
            partes.push({PartNumber: parte.part_number, ETag: etag});
            informar(hasta);
        }
        if (activo.signal.aborted) throw new DOMException("Carga cancelada", "AbortError");
        pendiente.archivos.set(ruta, {inicio,partes});
        await jsonPost(
            `/estudios/importaciones/${loteId}/archivos/${inicio.archivo_id}/completar/`,
            {partes, carga_token:inicio.carga_token},
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
        if (ruta.split("/").length > 100) throw new Error("La carpeta tiene demasiados niveles.");
        if (entry.isFile) return leerArchivo(entry, ruta);
        if (!entry.isDirectory) return [];

        const reader = entry.createReader();
        const entradas = [];
        let lote;
        do {
            lote = await leerLote(reader);
            entradas.push(...lote);
            if (entradas.length > 5000) throw new Error("La carpeta contiene demasiadas entradas.");
        } while (lote.length);

        const resultados = [];
        let cantidad = 0;
        for (const hija of entradas) {
            const archivos = await recorrerEntrada(hija, `${ruta}${entry.name}/`);
            cantidad += archivos.length;
            if (cantidad > 5000) throw new Error("El estudio supera los 5000 archivos.");
            resultados.push(archivos);
        }
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
        if (root.dataset.busy === "true" || cancelando) return;
        if (pendiente && filesEntrada !== pendiente.files) {mostrarError("Reintentá o cancelá la carpeta anterior antes de elegir otra."); return;}
        const files = Array.from(filesEntrada).filter(file => file.size > 0);
        if (!files.length || files.length > 5000) {
            mostrarError("Seleccioná una carpeta con entre 1 y 5000 archivos no vacíos.");
            return;
        }

        root.dataset.busy = "true";
        controller = new AbortController();
        const estaCarga = controller;
        cancelar.hidden = false; cancelar.disabled = false; reintentar.hidden = true; reintentar.disabled = false;
        button.disabled = input.disabled = true;
        errorBox.hidden = true;
        progress.hidden = false;
        activarEtapa("upload");
        const total = files.reduce((suma, archivo) => suma + archivo.size, 0);
        const primeraRuta = files[0]._docRelativePath || files[0].webkitRelativePath || "Estudio";
        const carpeta = primeraRuta.split("/")[0] || "Estudio";

        try {
            pendiente = pendiente || {files, completados:new Set(), archivos:new Map(), datos:{
                nombre_carpeta: carpeta,
                cantidad_archivos: files.length,
                tamano_total: total,
                solicitud_id:crypto.randomUUID(),
            }};
            const lote = pendiente.lote || await jsonPost("/estudios/importaciones/iniciar/", pendiente.datos);
            pendiente.lote = lote;
            const estadoResponse = await fetch(`/estudios/importaciones/${lote.importacion_id}/estado/`, {signal:AbortSignal.any([estaCarga.signal,AbortSignal.timeout(15000)])});
            if (!estadoResponse.ok) throw new Error("No se pudo consultar el estado de la carga.");
            const actual = await estadoResponse.json();
            if (["PROCESANDO", "PENDIENTE_CONFIRMACION", "CONFIRMADA", "ERROR"].includes(actual.estado)) {
                window.location.assign(lote.detalle_url + (window.DOC_UPLOAD_REDIRECT_APPEND || "")); return;
            }
            let acumulado = 0;
            for (let indice = 0; indice < files.length; indice += 1) {
                const archivo = files[indice];
                if (pendiente.completados.has(indice)) {acumulado += archivo.size; continue;}
                progressText.textContent = `${indice + 1} de ${files.length}: ${archivo.name}`;
                await subirArchivo(lote.importacion_id, archivo, bytes => {
                    const porcentaje = Math.round(((acumulado + bytes) / total) * 100);
                    progressBar.style.width = `${porcentaje}%`;
                    progressTrack.setAttribute("aria-valuenow", String(porcentaje));
                });
                pendiente.completados.add(indice);
                acumulado += archivo.size;
            }

            activarEtapa("analyze");
            progressTitle.textContent = "Detectando datos del paciente";
            progressText.textContent = "Leyendo la información de la carpeta…";
            const analisis = await jsonPost(`/estudios/importaciones/${lote.importacion_id}/analizar/`, {});
            progressBar.style.width = "100%";
            progressTrack.setAttribute("aria-valuenow", "100");
            activarEtapa("review");
            progressTitle.textContent = "Carga completa";
            progressText.textContent = "El análisis continúa en segundo plano…";
            window.location.assign(analisis.detalle_url + (window.DOC_UPLOAD_REDIRECT_APPEND || ""));
        } catch (error) {
            if (!cancelando && !estaCarga.signal.aborted) {
                mostrarError(error.message || "No se pudo importar la carpeta.");
                progressText.textContent = "Podés reintentar sin duplicar los archivos ya completados.";
                reintentar.hidden = false;
            }
            if (controller === estaCarga) root.dataset.busy = "false";
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
        if (root.dataset.busy === "true" || leyendo || pendiente) return;
        leyendo = true;
        dropZone.classList.remove("is-dragging");
        try {
            const files = await archivosDesdeCarpetaSoltada(evento.dataTransfer);
            await procesar(files);
        } catch (error) {
            mostrarError(error.message || "No pudimos leer la carpeta.");
        } finally {leyendo = false;}
    });

    window.DOC_manejarDropOdontologo = async function(e, nombreOdontologo, idOdontologo) {
        e.preventDefault();
        e.stopPropagation();
        
        // Remove styling class
        e.currentTarget.style.borderColor = "";
        e.currentTarget.style.backgroundColor = "";

        if (root.dataset.busy === "true") return;

        // Extraer entradas de forma síncrona antes del window.confirm
        // porque Chrome vacía el dataTransfer mientras el hilo está bloqueado.
        let entradas = [];
        if (e.dataTransfer && e.dataTransfer.items) {
            entradas = Array.from(e.dataTransfer.items)
                .map(item => typeof item.webkitGetAsEntry === 'function' ? item.webkitGetAsEntry() : null)
                .filter(Boolean);
        }

        if (entradas.length !== 1 || !entradas[0].isDirectory) {
            alert("Por favor, arrastrá una sola carpeta completa, no archivos sueltos.");
            return;
        }
        
        if (!window.confirm("¿Estás seguro que deseas cargar y asignar este estudio para " + nombreOdontologo + "?")) {
            return;
        }

        window.DOC_UPLOAD_REDIRECT_APPEND = "?derivante=" + idOdontologo;
        
        if (root.tagName === "DIALOG") {
            root.showModal();
        } else {
            root.hidden = false;
        }
        
        try {
            const files = await recorrerEntrada(entradas[0]);
            await procesar(files);
        } catch (err) {
            mostrarError(err.message);
        }
    };
});
