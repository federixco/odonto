import * as core from '@cornerstonejs/core';
import { metaData } from '@cornerstonejs/metadata';
import { init as initLoader, wadouri } from '@cornerstonejs/dicom-image-loader';
import { init as initTools, addTool, ToolGroupManager, PanTool, ZoomTool, TrackballRotateTool, Enums as ToolEnums } from '@cornerstonejs/tools';
import { planParalelo, escribirCorte } from './volumen.js';
import { CacheCortes, cargarEnParalelo } from './cortes-cache.js';

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
function abortable(promise, signal, timeout = 60000) {
  return new Promise((resolve, reject) => {
    const cleanup = () => { signal.removeEventListener('abort', abort); clearTimeout(timer); };
    const abort = () => { cleanup(); reject(new DOMException('Cancelado', 'AbortError')); };
    const timer = setTimeout(() => { cleanup(); reject(new Error('red')); }, timeout);
    signal.addEventListener('abort', abort, { once: true });
    promise.then(value => { cleanup(); resolve(value); }, error => { cleanup(); reject(error); });
    if (signal.aborted) abort();
  });
}

export async function abrirDicom(element, serie, mode, ctx) {
  initialize(ctx.limits);
  const requests = new Set();
  const session = { ...ctx, requests };
  current = session;
  const id = `doc-${crypto.randomUUID()}`;
  const imageIds = serie.archivos.flatMap(a => Array.from({ length: a.frames }, (_, n) => {
    const url = new URL(a.url, location.origin);
    // Aislar resoluciones tardías de una apertura cancelada de la siguiente.
    url.searchParams.set('apertura', id);
    if (a.frames > 1) url.searchParams.set('frame', n + 1);
    return `wadouri:${url.href}`;
  }));
  const costs = serie.archivos.flatMap(a => Array(a.frames).fill(a.bytes * 2 + (a.decodedBytes || ctx.limits.imageBytes) * 3));
  const deviceGiB = Number(navigator.deviceMemory) || 4;
  const budget = Math.min(ctx.limits.volumeBytes, Math.max(1, deviceGiB) * 64 * 1024 * 1024);
  const baseLoads = new Map();
  const bases = imageIds.map(imageId => `wadouri:${wadouri.parseImageId(imageId).url}`);
  let stackCache, activeSlice = 0;
  const engine = new core.RenderingEngine(id);
  const group = ToolGroupManager.createToolGroup(id);
  let volume, viewport, disposed = false, observer, pendingSlice = null, navigating = false;
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    pendingSlice = null;
    ctx.signal.removeEventListener('abort', dispose);
    observer?.disconnect();
    stackCache?.dispose();
    volume?.cancelLoading?.();
    for (const xhr of requests) xhr.abort();
    requests.clear();
    core.imageLoader.cancelLoadAll();
    ToolGroupManager.destroyToolGroup(id);
    engine.destroy();
    volume?.destroy(); volume = null;
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
    check();
    if (core.cache.isLoaded(imageId)) return core.cache.getImage(imageId);
    const base = `wadouri:${wadouri.parseImageId(imageId).url}`;
    // Los frames del mismo objeto comparten la descarga de metadatos/píxeles.
    if (baseLoads.has(base)) {
      await abortable(baseLoads.get(base), ctx.signal);
      check();
    }
    // En 5.11.4 loadAndCacheImage no observa el rechazo de putImageLoadObject.
    // Esperamos ambas promesas explícitamente antes de pasarlas al viewport.
    const promise = core.imageLoader.loadImage(imageId).then(image => {
      if (disposed) releaseImage(imageId);
      check(); return image;
    });
    baseLoads.set(base, promise);
    const object = { promise, decache() { wadouri.dataSetCacheManager.unload(wadouri.parseImageId(imageId).url); } };
    try {
      if (!core.cache.getImageLoadObject(imageId)) await abortable(core.cache.putImageLoadObject(imageId, object), ctx.signal);
      else await abortable(promise, ctx.signal);
    } finally {
      if (baseLoads.get(base) === promise) baseLoads.delete(base);
    }
    check();
    const image = core.cache.getImage(imageId);
    if (!image) throw new Error('formato');
    return image;
  };
  const releaseImage = imageId => {
    if (core.cache.getImageLoadObject(imageId)) core.cache.removeImageLoadObject(imageId);
    const base = `wadouri:${wadouri.parseImageId(imageId).url}`;
    const shared = imageIds.some((other, i) => bases[i] === base && other !== imageId && core.cache.getImageLoadObject(other));
    for (const type of Object.values(core.Enums.MetadataModules)) {
      if (imageId !== base || !shared) metaData.clearQuery(type, imageId);
      if (!shared) metaData.clearQuery(type, base);
    }
  };
  stackCache = mode === 'cortes' ? new CacheCortes({
    costs, budget, concurrency: ctx.limits.concurrency,
    load: index => loadSafe(imageIds[index]), release: index => releaseImage(imageIds[index]),
    onError(e) {
      if (!disposed && errorCode(e) === 'sesion') { dispose(); ctx.error?.('sesion'); }
    },
  }) : null;
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
      if (!serie.volumen || !serie.vista_3d) throw new Error('formato');
      // Consultar el límite GPU sin conservar un segundo contexto.
      const probe = document.createElement('canvas');
      const gl = probe.getContext('webgl2');
      if (!gl) throw new Error('webgl');
      const maxDimension = gl.getParameter(gl.MAX_3D_TEXTURE_SIZE);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      const { plan, concurrency } = planParalelo(serie.vista_3d, budget, maxDimension, ctx.limits.concurrency);
      if (imageIds.length !== plan.dimensiones_originales[2]) throw new Error('formato');
      ctx.quality?.(plan.reducida, plan.dimensiones);
      let scalarData = new Float32Array(plan.bytes / 4);
      let completed = 0;
      ctx.status(`Cargando cortes para el volumen… 0 / ${plan.indices.length}`, 0);
      // Ventana paralela acotada; cada corte se escribe en su posición espacial.
      // Un corte seleccionado corrupto invalida la vista, no se rellena con ceros.
      await cargarEnParalelo(plan.indices.length, concurrency, ctx.signal, async z => {
        check();
        const imageId = imageIds[plan.indices[z]];
        try {
          const image = await loadSafe(imageId);
          check(); escribirCorte(scalarData, z, plan, image);
        } finally { releaseImage(imageId); }
        completed++;
        ctx.status(`Cargando cortes para el volumen… ${completed} / ${plan.indices.length}`, Math.round(completed / plan.indices.length * 95));
        // Dar oportunidad de pintar el progreso y procesar Cerrar/Cancelar.
        await new Promise(resolve => setTimeout(resolve, 0));
      });
      check(); ctx.status('Construyendo volumen…', 96);
      // "derived:" evita que Cornerstone intente recargar estos cortes locales
      // con el loader HTTP al calcular el VOI inicial del actor.
      volume = core.volumeLoader.createLocalVolume(`derived:doc-preview:${id}`, {
        scalarData, dimensions: plan.dimensiones, spacing: plan.espaciado,
        origin: plan.origen, direction: plan.direccion,
        metadata: { ...plan.metadata, BitsAllocated: 32, BitsStored: 32, HighBit: 31,
          SamplesPerPixel: 1, PhotometricInterpretation: 'MONOCHROME2', PixelRepresentation: 1 },
      });
      volume.isPreScaled = true;
      scalarData = null; // Las vistas locales comparten el buffer, no lo duplican.
      check();
      await core.setVolumesForViewports(engine, [{ volumeId: volume.volumeId }], [id]);
      check(); viewport.setProperties({ preset: 'CT-Bone' });
    } else {
      ctx.status('Cargando primer corte…');
      stackCache.protect([0]);
      await stackCache.get(0);
      await abortable(viewport.setStack(imageIds), ctx.signal);
      check(); ctx.slice?.(1, imageIds.length);
    }
    viewport.resetCamera(); viewport.render();
    observer = new ResizeObserver(() => { if (!disposed) { engine.resize(true, false); viewport.render(); } });
    observer.observe(element);
    ctx.status(mode === 'volumen' ? 'Volumen listo · Exploración visual' : 'Cortes listos', 100);
    stackCache?.prefetch(0);
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
            stackCache.protect([activeSlice, index]);
            if (!core.cache.isLoaded(imageIds[index])) ctx.status('Cargando corte…');
            await stackCache.get(index);
            check();
            if (pendingSlice !== null) continue; // Dar prioridad al último salto.
            await abortable(viewport.setImageIdIndex(index), ctx.signal);
            check(); viewport.render(); ctx.slice?.(index + 1, imageIds.length);
            activeSlice = index;
            stackCache.protect([index]);
            stackCache.prefetch(index);
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
