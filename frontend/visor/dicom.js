import * as core from '@cornerstonejs/core';
import { metaData } from '@cornerstonejs/metadata';
import { init as initLoader, wadouri } from '@cornerstonejs/dicom-image-loader';
import { init as initTools, addTool, ToolGroupManager, PanTool, ZoomTool, TrackballRotateTool, Enums as ToolEnums } from '@cornerstonejs/tools';

let initialized = false;
let current = null;

function initialize(limits) {
  if (!initialized) {
    // Los mensajes de la biblioteca pueden incluir datasets; la UI usa códigos acotados.
    core.utilities.logger.cs3dLog.setLevel('silent');
    core.init({ rendering: { useCPURendering: false, webGlContextCount: 1 } });
    initTools();
    for (const tool of [PanTool, ZoomTool, TrackballRotateTool]) addTool(tool);
    initLoader({
      maxWebWorkers: Math.min(2, navigator.hardwareConcurrency || 1),
      open(xhr, url) {
        if (!current || current.signal.aborted) throw new DOMException('Cancelado', 'AbortError');
        xhr.open('GET', url, true);
        xhr.withCredentials = false; // Cookie al Django del mismo origen; nunca al bucket.
        xhr.timeout = 60000;
        const session = current;
        session.requests.add(xhr);
        xhr.addEventListener('loadend', () => session.requests.delete(xhr), { once: true });
        xhr.addEventListener('timeout', () => xhr.abort(), { once: true });
        xhr.addEventListener('progress', e => {
          if (e.loaded > session.limits.imageBytes) { session.failure = 'memoria'; xhr.abort(); }
        });
      },
      errorInterceptor() { /* La UI muestra códigos; no URLs firmadas ni dataset en logs. */ },
    });
    initialized = true;
  }
  core.cache.setMaxCacheSize(limits.volumeBytes);
  for (const pool of [core.imageLoadPoolManager, core.imageRetrievalPoolManager]) {
    for (const type of Object.values(core.Enums.RequestType)) pool?.setMaxSimultaneousRequests(type, limits.concurrency);
  }
}

/** Espera cancelable: las tareas tardías no pueden volver a montar un viewport. */
function abortable(promise, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('Cancelado', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
    if (signal.aborted) abort();
  });
}

export async function abrirDicom(element, serie, mode, ctx) {
  initialize(ctx.limits);
  const requests = new Set();
  const session = { ...ctx, requests };
  current = session;
  const id = `doc-${crypto.randomUUID()}`;
  const imageIds = serie.archivos.flatMap(a => Array.from({ length: a.frames }, (_, n) => `wadouri:${new URL(a.url, location.origin).href}${a.frames > 1 ? `?frame=${n+1}` : ''}`));
  const engine = new core.RenderingEngine(id);
  const group = ToolGroupManager.createToolGroup(id);
  let volume, viewport, disposed = false, observer, pendingSlice = null, navigating = false;
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    pendingSlice = null;
    ctx.signal.removeEventListener('abort', dispose);
    observer?.disconnect();
    volume?.cancelLoading();
    for (const xhr of requests) xhr.abort();
    requests.clear();
    core.imageLoader.cancelLoadAll();
    ToolGroupManager.destroyToolGroup(id);
    engine.destroy();
    core.cache.purgeCache();
    wadouri.dataSetCacheManager.purge();
    for (const type of Object.values(core.Enums.MetadataModules)) metaData.clear(type);
    core.getWebWorkerManager().terminate('dicomImageLoader');
    if (current === session) current = null;
    element.replaceChildren();
  };
  ctx.signal.addEventListener('abort', dispose, { once: true });
  const check = () => {
    ctx.signal.throwIfAborted();
    if (disposed) throw new DOMException('Cancelado', 'AbortError');
  };
  const errorCode = error => {
    if (session.failure) return session.failure;
    const source = error?.error || error;
    if (typeof source?.status === 'number') return [401,403].includes(source.status) ? 'sesion' : 'red';
    return ['red','memoria','formato','webgl'].includes(source?.message) ? source.message : 'formato';
  };
  const loadSafe = async imageId => {
    if (core.cache.isLoaded(imageId)) return;
    // En 5.11.4 loadAndCacheImage no observa el rechazo de putImageLoadObject.
    // Esperamos ambas promesas explícitamente antes de pasarlas al viewport.
    const promise = core.imageLoader.loadImage(imageId);
    const object = { promise, decache() { wadouri.dataSetCacheManager.unload(wadouri.parseImageId(imageId).url); } };
    if (!core.cache.getImageLoadObject(imageId)) await abortable(core.cache.putImageLoadObject(imageId, object), ctx.signal);
    else await abortable(promise, ctx.signal);
    check();
  };
  try {
    engine.enableElement({ viewportId: id, type: mode === 'volumen' ? core.Enums.ViewportType.VOLUME_3D : core.Enums.ViewportType.STACK,
      element, defaultOptions: { background: [.035, .055, .075] } });
    viewport = engine.getViewport(id);
    group.addViewport(id, id);
    for (const tool of [PanTool, ZoomTool, TrackballRotateTool]) group.addTool(tool.toolName);
    const primary = mode === 'volumen' ? TrackballRotateTool : PanTool;
    group.setToolActive(primary.toolName, { bindings: [{ mouseButton: ToolEnums.MouseBindings.Primary }, { numTouchPoints: 1 }] });
    group.setToolActive(ZoomTool.toolName, { bindings: [{ mouseButton: ToolEnums.MouseBindings.Secondary }, { numTouchPoints: 2 }] });
    if (mode === 'volumen') group.setToolActive(PanTool.toolName, { bindings: [{ mouseButton: ToolEnums.MouseBindings.Auxiliary }] });
    if (mode === 'volumen') {
      if (!serie.volumen || serie.memoria_estimada > ctx.limits.volumeBytes) throw new Error('memoria');
      // Metadatos y decodificación verificados antes de reconstruir: nunca unir cortes fallidos.
      let cursor = 0, loaded = 0;
      ctx.status('Cargando cortes para el volumen…', 0);
      await abortable(Promise.all(Array.from({ length: ctx.limits.concurrency }, async () => {
        while (cursor < imageIds.length) {
          check();
          await loadSafe(imageIds[cursor++]);
          check(); loaded++; ctx.status('Cargando cortes para el volumen…', Math.round(loaded / imageIds.length * 95));
        }
      })), ctx.signal);
      check(); ctx.status('Construyendo volumen…', 96);
      volume = await abortable(core.volumeLoader.createAndCacheVolume(`cornerstoneStreamingImageVolume:${id}`, { imageIds }), ctx.signal);
      check();
      await abortable(new Promise((resolve, reject) => volume.load(s => {
        if (!s.success) reject(new Error('formato'));
        else if (s.framesLoaded === imageIds.length) resolve();
      })), ctx.signal);
      check();
      await core.setVolumesForViewports(engine, [{ volumeId: volume.volumeId }], [id]);
      check(); viewport.setProperties({ preset: 'CT-Bone' });
    } else {
      ctx.status('Cargando primer corte…');
      await loadSafe(imageIds[0]);
      await abortable(viewport.setStack(imageIds), ctx.signal);
      check(); ctx.slice?.(1, imageIds.length);
    }
    viewport.resetCamera(); viewport.render();
    observer = new ResizeObserver(() => { if (!disposed) { engine.resize(true, false); viewport.render(); } });
    observer.observe(element);
    ctx.status(mode === 'volumen' ? 'Volumen listo · Exploración visual' : 'Cortes listos', 100);
    return {
      reset() { viewport.resetCamera(); viewport.render(); },
      zoom(factor) { const camera = viewport.getCamera(); viewport.setCamera({ parallelScale: camera.parallelScale * factor }); viewport.render(); },
      rotate() { if (mode === 'volumen') { const cam = viewport.getVtkActiveCamera(); cam.azimuth(15); viewport.render(); } },
      async slice(number) {
        if (mode !== 'cortes' || disposed || !Number.isFinite(number)) return;
        pendingSlice = Math.max(0, Math.min(imageIds.length - 1, Math.round(number) - 1));
        if (navigating) return;
        navigating = true;
        try {
          // Una carga por vez: los movimientos intermedios ceden al último corte elegido.
          while (pendingSlice !== null && !disposed) {
            const index = pendingSlice; pendingSlice = null;
            ctx.status('Cargando corte…');
            await loadSafe(imageIds[index]);
            await abortable(viewport.setImageIdIndex(index), ctx.signal);
            check(); viewport.render(); ctx.slice?.(index + 1, imageIds.length);
            // El cache del loader también retiene bytes originales: conservar solo este corte.
            const activeBase = `wadouri:${wadouri.parseImageId(imageIds[index]).url}`;
            for (const image of imageIds) {
              if (image !== imageIds[index] && core.cache.getImageLoadObject(image)) {
                core.cache.removeImageLoadObject(image);
                const base = `wadouri:${wadouri.parseImageId(image).url}`;
                for (const type of Object.values(core.Enums.MetadataModules)) {
                  metaData.clearQuery(type, image);
                  // Multiframe comparte bytes entre frames; liberarlos al salir del objeto.
                  if (base !== activeBase) metaData.clearQuery(type, base);
                }
              }
            }
          }
          check(); ctx.status('Cortes listos', 100);
        } catch (e) { if (!disposed && e.name !== 'AbortError') ctx.error?.(errorCode(e)); }
        finally { navigating = false; }
      },
      dispose,
    };
  } catch (e) {
    const fallo = ctx.signal.aborted || e.name === 'AbortError'
      ? new DOMException('Cancelado', 'AbortError') : new Error(errorCode(e));
    dispose(); throw fallo;
  }
}
