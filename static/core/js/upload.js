"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const uploader = document.querySelector("[data-estudio-uploader]");
    if (!uploader) return;

    const estudioId = uploader.dataset.estudioId;
    const fileInput = document.getElementById("file-input");
    const selectButton = document.getElementById("file-select-button");
    const dropZone = document.getElementById("drop-zone");
    const progressContainer = document.getElementById("upload-progress-container");
    const progressTrack = document.querySelector(".progress-bar-wrap");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const uploadSuccess = document.getElementById("upload-success");
    const uploadError = document.getElementById("upload-error");
    const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
    const maxRetries = 3;

    function mostrarError(mensaje) {
        uploadError.textContent = mensaje;
        uploadError.hidden = false;
        uploadSuccess.hidden = true;
    }

    async function leerError(response, alternativa) {
        try {
            const data = await response.json();
            return data.error || alternativa;
        } catch (_) {
            return alternativa;
        }
    }

    function subirParte(url, bloque, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("PUT", url, true);
            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) onProgress(event.loaded);
            };
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    const etag = xhr.getResponseHeader("ETag");
                    if (etag) resolve(etag);
                    else reject(new Error("El almacenamiento no expuso el ETag."));
                } else {
                    reject(new Error(`La parte respondió HTTP ${xhr.status}.`));
                }
            };
            xhr.onerror = () => reject(new Error("Se interrumpió la conexión."));
            xhr.onabort = () => reject(new Error("La carga fue cancelada."));
            xhr.send(bloque);
        });
    }

    async function cancelarArchivo(archivoId) {
        if (!archivoId) return;
        try {
            await fetch(`/archivos/cancelar/${archivoId}/`, {
                method: "POST",
                headers: {"X-CSRFToken": csrfToken},
            });
        } catch (_) {
            // El backend y la política de limpieza de S3 resolverán cargas huérfanas.
        }
    }

    async function subirArchivo(file, onProgress) {
        let archivoId = null;
        try {
            const initResponse = await fetch(`/archivos/iniciar/${estudioId}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    nombre_archivo: file.name,
                    tamano: file.size,
                }),
            });
            if (!initResponse.ok) {
                throw new Error(await leerError(initResponse, "No se pudo iniciar la carga."));
            }

            const initData = await initResponse.json();
            archivoId = initData.archivo_id;
            const partSize = initData.part_size;
            const uploadedParts = [];

            for (const partInfo of initData.partes) {
                const start = (partInfo.part_number - 1) * partSize;
                const end = Math.min(start + partSize, file.size);
                const bloque = file.slice(start, end);
                let etag = null;

                for (let intento = 1; intento <= maxRetries && !etag; intento += 1) {
                    try {
                        etag = await subirParte(partInfo.url, bloque, (bytesParte) => {
                            onProgress(Math.min(start + bytesParte, file.size));
                        });
                    } catch (error) {
                        if (intento === maxRetries) throw error;
                    }
                }
                uploadedParts.push({PartNumber: partInfo.part_number, ETag: etag});
                onProgress(end);
            }

            const completeResponse = await fetch(`/archivos/completar/${archivoId}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({partes: uploadedParts}),
            });
            if (!completeResponse.ok) {
                throw new Error(
                    await leerError(completeResponse, "No se pudo verificar el archivo.")
                );
            }
            return archivoId;
        } catch (error) {
            await cancelarArchivo(archivoId);
            throw error;
        }
    }

    async function procesarArchivos(fileList) {
        const files = Array.from(fileList);
        if (!files.length) return;

        selectButton.disabled = true;
        fileInput.disabled = true;
        uploadError.hidden = true;
        uploadSuccess.hidden = true;
        progressContainer.hidden = false;
        let bytesCompletados = 0;
        const bytesTotales = files.reduce((total, file) => total + file.size, 0);

        try {
            for (let index = 0; index < files.length; index += 1) {
                const file = files[index];
                progressText.textContent = `Subiendo ${index + 1} de ${files.length}: ${file.name}`;
                await subirArchivo(file, (bytesArchivo) => {
                    const porcentaje = Math.round(
                        ((bytesCompletados + bytesArchivo) / bytesTotales) * 100
                    );
                    progressBar.style.width = `${porcentaje}%`;
                    progressTrack.setAttribute("aria-valuenow", String(porcentaje));
                });
                bytesCompletados += file.size;
            }
            progressBar.style.width = "100%";
            progressTrack.setAttribute("aria-valuenow", "100");
            progressText.textContent = "Carga y verificación completadas.";
            uploadSuccess.hidden = false;
            window.setTimeout(() => window.location.reload(), 900);
        } catch (error) {
            mostrarError(error.message || "No se pudo completar la carga.");
            progressContainer.hidden = true;
            selectButton.disabled = false;
            fileInput.disabled = false;
        }
    }

    selectButton.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (event) => procesarArchivos(event.target.files));
    dropZone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropZone.classList.add("is-dragging");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragging"));
    dropZone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropZone.classList.remove("is-dragging");
        procesarArchivos(event.dataTransfer.files);
    });
});
