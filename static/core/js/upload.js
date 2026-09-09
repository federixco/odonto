document.addEventListener("DOMContentLoaded", function() {
    const CHUNK_SIZE = 10 * 1024 * 1024; // 10MB
    const MAX_RETRIES = 3;

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrfToken = getCookie("csrftoken");

    async function uploadFile(file, estudioId, csrfToken, onProgress, onSuccess, onError) {
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
        
        // 1. Iniciar carga
        try {
            const initRes = await fetch(`/archivos/iniciar/${estudioId}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({
                    nombre_archivo: file.name,
                    formato: file.name.split('.').pop(),
                    categoria: "IMAGEN", // TODO: deducir de extensión
                    tamano: file.size,
                    cantidad_partes: totalChunks,
                    content_type: file.type || "application/octet-stream"
                })
            });
            
            if (!initRes.ok) throw new Error("Fallo al iniciar upload");
            
            const initData = await initRes.json();
            const { archivo_id, upload_id, clave_objeto, partes } = initData;
            
            let uploadedParts = [];
            
            // 2. Subir chunks
            for (let i = 0; i < partes.length; i++) {
                const partInfo = partes[i];
                const start = (partInfo.part_number - 1) * CHUNK_SIZE;
                const end = Math.min(start + CHUNK_SIZE, file.size);
                const chunk = file.slice(start, end);
                
                let retries = 0;
                let success = false;
                
                while (retries < MAX_RETRIES && !success) {
                    try {
                        const etag = await uploadChunk(partInfo.url, chunk, onProgress, start, file.size);
                        uploadedParts.push({
                            PartNumber: partInfo.part_number,
                            ETag: etag
                        });
                        success = true;
                    } catch (e) {
                        retries++;
                        if (retries >= MAX_RETRIES) {
                            throw new Error(`Fallo al subir parte ${partInfo.part_number}`);
                        }
                    }
                }
            }
            
            // 3. Completar
            const completeRes = await fetch(`/archivos/completar/${archivo_id}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({ partes: uploadedParts })
            });
            
            if (!completeRes.ok) throw new Error("Fallo al completar upload");
            
            onSuccess(archivo_id);
            
        } catch (error) {
            onError(error.message);
        }
    }

    function uploadChunk(url, chunk, onProgress, startOffset, totalSize) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("PUT", url, true);
            
            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const totalUploaded = startOffset + e.loaded;
                    const percent = Math.round((totalUploaded / totalSize) * 100);
                    onProgress(percent);
                }
            };
            
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    const etag = xhr.getResponseHeader("ETag");
                    resolve(etag);
                } else {
                    reject(new Error("Error HTTP " + xhr.status));
                }
            };
            
            xhr.onerror = function() {
                reject(new Error("Error de red"));
            };
            
            xhr.send(chunk);
        });
    }

    window.UploadManager = {
        startUpload: function(file, estudioId, progressCallback, successCallback, errorCallback) {
            uploadFile(file, estudioId, csrfToken, progressCallback, successCallback, errorCallback);
        }
    };
});
