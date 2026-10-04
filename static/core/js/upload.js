"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-estudio-uploader]");
    if (!root) return;
    const fileInput = document.getElementById("file-input"), selectButton = document.getElementById("file-select-button");
    const dropZone = document.getElementById("drop-zone"), progress = document.getElementById("upload-progress-container");
    const bar = document.getElementById("progress-bar"), text = document.getElementById("progress-text");
    const track = document.querySelector(".progress-bar-wrap"), errorBox = document.getElementById("upload-error");
    const success = document.getElementById("upload-success"), replacement = document.getElementById("replacement-file-select");
    const csrf = document.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    const cancel = document.createElement("button"), retry = document.createElement("button");
    cancel.type = retry.type = "button"; cancel.className = "button button-secondary"; retry.className = "button";
    cancel.textContent = "Cancelar archivo en carga"; retry.textContent = "Reintentar"; retry.hidden = true; progress.append(cancel,retry);
    let pending, busy = false, controller, currentFile, currentItem, cancelando = false;
    function controls(disabled) {selectButton.disabled = fileInput.disabled = disabled; if (replacement) replacement.disabled = disabled;}
    function error(message) {errorBox.textContent = message; errorBox.hidden = false;}
    async function json(url, body, independent = false) {
        const active = controller;
        for (let attempt = 0; attempt < 3; attempt += 1) {
            try {
                const response = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json","X-CSRFToken":csrf},
                    body:JSON.stringify(body), signal:independent ? AbortSignal.timeout(30000) : AbortSignal.any([active.signal,AbortSignal.timeout(30000)])});
                const data = await response.json();
                if (!response.ok) {const e = new Error(data.error || "No se pudo continuar."); e.retry = response.status >= 500 || data.reintentable === true; throw e;}
                return data;
            } catch(e) {
                if ((!independent && active.signal.aborted) || e.retry === false || attempt === 2) throw e;
                await new Promise(resolve => setTimeout(resolve, 800 * (2 ** attempt)));
            }
        }
    }
    function part(url, blob, progressPart, signal) {
        return new Promise((resolve,reject) => {
            const xhr = new XMLHttpRequest(); xhr.open("PUT",url); xhr.timeout = 120000;
            const abort = () => xhr.abort();
            if (signal.aborted) {reject(new DOMException("Cancelado","AbortError")); return;}
            signal.addEventListener("abort",abort,{once:true});
            xhr.onloadend = () => signal.removeEventListener("abort",abort);
            xhr.onabort = () => reject(new DOMException("Cancelado","AbortError"));
            xhr.onerror = xhr.ontimeout = () => reject(new Error("Conexión interrumpida o tiempo agotado."));
            xhr.upload.onprogress = e => {if (e.lengthComputable) progressPart(e.loaded);};
            xhr.onload = () => {const etag = xhr.getResponseHeader("ETag"); if (xhr.status >= 200 && xhr.status < 300 && etag) resolve(etag); else reject(new Error("No se confirmó la parte."));};
            xhr.send(blob);
        });
    }
    async function upload(item,onProgress,independent = false) {
        const active = controller;
        if (item.init && item.parts) {
            currentFile = item.init.archivo_id;
            try {
                await json(`/archivos/completar/${currentFile}/`, {partes:item.parts,carga_token:item.init.carga_token});
                onProgress(item.file.size); return;
            } catch(error) {
                if (active.signal.aborted || error.retry !== false) throw error;
                item.init = item.parts = null;
            }
        }
        const init = await json(`/archivos/iniciar/${root.dataset.estudioId}/`, item.data, independent);
        item.init = init;
        currentFile = init.archivo_id;
        if (init.status === "completo") {onProgress(item.file.size); return;}
        const parts = [];
        for (const info of init.partes) {
            const start = (info.part_number - 1) * init.part_size, end = Math.min(start + init.part_size,item.file.size);
            let etag;
            for(let attempt = 0; attempt < 3; attempt += 1) {
                if (active.signal.aborted) throw new DOMException("Cancelado", "AbortError");
                try {etag = await part(info.url,item.file.slice(start,end),n => onProgress(start+n),active.signal); break;}
                catch(e) {if (active.signal.aborted || attempt === 2) throw e; await new Promise(r => setTimeout(r,800 * (2 ** attempt)));}
            }
            parts.push({PartNumber:info.part_number,ETag:etag}); onProgress(end);
        }
        if (active.signal.aborted) throw new DOMException("Cancelado", "AbortError");
        item.parts = parts;
        await json(`/archivos/completar/${init.archivo_id}/`,{partes:parts,carga_token:init.carga_token});
    }
    async function process(files) {
        if (busy || cancelando || pending && files) return;
        if (files) {
            const list = Array.from(files).filter(f => f.size > 0);
            if (!list.length) return;
            if (replacement?.value && list.length !== 1) {error("Seleccioná un solo archivo para reemplazar."); return;}
            pending = list.map(file => ({file,data:{nombre_archivo:file.name,tamano:file.size,archivo_reemplazado:replacement?.value || null,solicitud_id:crypto.randomUUID()}}));
        }
        if (!pending) return;
        busy = true; controller = new AbortController(); const active = controller;
        controls(true); errorBox.hidden = success.hidden = true; progress.hidden = false; retry.hidden = true; cancel.hidden = false; cancel.disabled = false;
        const total = pending.reduce((n,item) => n+item.file.size,0); let loaded = 0;
        try {
            for (const item of pending) {
                currentItem = item;
                text.textContent = `Cargando ${item.file.name}`; currentFile = null;
                if (item.done) {loaded += item.file.size; continue;}
                await upload(item,n => {const percent = Math.round((loaded+n)/total*100); bar.style.width = `${percent}%`; track.setAttribute("aria-valuenow",String(percent));});
                item.done = true;
                loaded += item.file.size;
            }
            success.hidden = false; text.textContent = "Carga verificada."; pending = null; cancel.hidden = true;
            setTimeout(() => location.reload(),900);
        } catch(e) {
            if (!active.signal.aborted) {error(e.message); retry.hidden = false; text.textContent = "Reintentá sin duplicar los archivos completados.";}
        } finally {if (controller === active) busy = false;}
    }
    retry.addEventListener("click",() => process());
    cancel.addEventListener("click",async () => {
        if (!pending || !confirm("¿Cancelar el archivo en carga? Los completados se conservarán.")) return;
        cancelando = true; controller?.abort(); cancel.disabled = true; retry.disabled = true;
        try {
            if (!currentFile) {
                const item = currentItem || pending.find(item => !item.done) || pending[0];
                const init = await json(`/archivos/iniciar/${root.dataset.estudioId}/`,item.data,true); currentFile = init.archivo_id;
            }
            const data = await json(`/archivos/cancelar/${currentFile}/`,{},true);
            pending = null; text.textContent = data.status === "completo" ? "El archivo ya se había completado y se conservó." : "Carga cancelada.";
            cancel.hidden = retry.hidden = true; controls(false); fileInput.value = "";
            cancelando = false;
        } catch(e) {error("No se confirmó la cancelación. Reintentá Cancelar: "+e.message); cancel.disabled = false;}
        finally {retry.disabled = false;}
    });
    selectButton.addEventListener("click",() => fileInput.click());
    fileInput.addEventListener("change",e => process(e.target.files));
    dropZone.addEventListener("dragover",e => {e.preventDefault(); if (!busy) dropZone.classList.add("is-dragging");});
    dropZone.addEventListener("dragleave",() => dropZone.classList.remove("is-dragging"));
    dropZone.addEventListener("drop",e => {e.preventDefault(); dropZone.classList.remove("is-dragging"); process(e.dataTransfer.files);});
    document.querySelectorAll("[data-replacement-target]").forEach(button => button.addEventListener("click",() => {
        if (busy || pending || !replacement) return; replacement.value = button.dataset.replacementTarget;
        const manual = document.querySelector(".manual-upload-option"); if (manual) {manual.open = true; manual.scrollIntoView({behavior:"smooth"});}
    }));
});
