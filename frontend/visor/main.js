import './visor.css';
import { comprobarWebGL, json } from './common.js';

const $ = id => document.getElementById(id);
const config = JSON.parse($('visor-config').textContent);
const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
let controller, viewer, items = [], selected, mode, generation = 0, polling, reportSent = false;
let currentSlice = 1;
let catalogController, selectionMade = false;
const controls = ['reset', 'zoom-in', 'zoom-out', 'rotate'];
const messages = {
  webgl: 'No se pudo iniciar la aceleración 3D. Probá otro navegador o equipo con WebGL 2.',
  memoria: 'Este archivo excede la capacidad prevista del visor. Elegí otro contenido o consultá al centro.',
  formato: 'No se pudo interpretar el archivo. Su formato o geometría no es compatible.',
  sesion: 'La sesión o el permiso ya no están vigentes. Volvé al estudio e ingresá nuevamente.',
  red: 'No se pudo cargar el contenido. Revisá la conexión y volvé a intentar; se comprobará de nuevo tu acceso.',
};
function status(text, progress) {
  $('estado').textContent = text;
  $('estado').parentElement.classList.remove('error');
  $('progreso').hidden = progress === 100;
  if (typeof progress === 'number') $('progreso').value = progress; else $('progreso').removeAttribute('value');
}
async function report(resultado, codigo = '') {
  if (reportSent) return;
  try {
    await json(config.eventos, { method: 'POST', headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: config.token, resultado, modo: mode, codigo }) });
    reportSent = true;
  } catch { /* Una falla de telemetría no debe ocultar el estudio. */ }
}
function error(code) {
  if (code === 'sesion') close();
  status(messages[code] || messages.formato, 100);
  $('estado').parentElement.classList.add('error'); $('reintentar').hidden = code === 'sesion';
  void report('fallo', ['red', 'memoria', 'formato', 'webgl'].includes(code) ? code : 'desconocido');
}
function close() {
  generation++;
  controller?.abort(); viewer?.dispose(); viewer = null;
  $('lienzo').replaceChildren(); $('vacio').hidden = false; $('slice-controls').hidden = true;
  for (const id of controls) $(id).disabled = true;
  $('reintentar').hidden = true;
  status('Vista cerrada. Podés elegir otro contenido.', 100);
}
async function open(newMode) {
  if (!selected) return;
  close(); mode = newMode;
  const gen = generation;
  controller = new AbortController(); const signal = controller.signal;
  const guardedStatus = (...args) => { if (gen === generation) status(...args); };
  $('vacio').hidden = true; $('reintentar').hidden = true;
  $('cortes').setAttribute('aria-pressed', mode === 'cortes'); $('volumen').setAttribute('aria-pressed', mode === 'volumen');
  try {
    comprobarWebGL(); guardedStatus('Preparando visualizador…');
    const ctx = { signal, limits: config.limites, status: guardedStatus,
      error(code) { if (gen === generation) error(code); },
      slice(n, total) {
        if (gen !== generation) return;
        currentSlice = n; $('slice').max = total; $('slice').value = n; $('slice-value').textContent = `${n} / ${total}`;
      } };
    let next;
    if (mode === 'modelo') {
      const { abrirModelo } = await import('./modelos.js'); signal.throwIfAborted();
      next = await abrirModelo($('lienzo'), selected, ctx);
    } else {
      const serie = await json(selected.url, { signal });
      const { abrirDicom } = await import('./dicom.js'); signal.throwIfAborted();
      next = await abrirDicom($('lienzo'), serie, mode, ctx);
    }
    if (gen !== generation) { next.dispose(); return; }
    viewer = next;
    for (const id of controls) $(id).disabled = false;
    $('rotate').disabled = mode === 'cortes'; $('slice-controls').hidden = mode !== 'cortes';
    void report('renderizado');
  } catch (e) { if (gen === generation && e.name !== 'AbortError') { controller.abort(); error(e.message); } }
}
async function catalogo(retry = false) {
  clearTimeout(polling);
  catalogController?.abort();
  catalogController = new AbortController();
  const signal = catalogController.signal;
  try {
    const url = new URL(config.catalogo, location.origin);
    const requested = new URLSearchParams(location.search).get('archivo');
    if (requested) url.searchParams.set('archivo', requested);
    const data = await json(url, { signal, ...(retry ? { method: 'POST', headers: { 'X-CSRFToken': csrf } } : {}) });
    signal.throwIfAborted();
    const previous = $('contenido-selector').value;
    items = [...data.modelos.map(x => ({ ...x, kind: 'modelo', key: `m-${x.id}` })), ...data.series.map(x => ({ ...x, kind: 'serie', key: `s-${x.id}` }))];
    $('contenido-selector').replaceChildren(new Option('Seleccioná un contenido', ''));
    for (const item of items) {
      const option = new Option(item.kind === 'modelo' ? `${item.formato} · ${item.nombre}` : `${item.nombre} · ${item.frames} cortes`, item.key);
      option.disabled = item.disponible === false; $('contenido-selector').add(option);
    }
    if (items.some(i => i.key === previous)) $('contenido-selector').value = previous;
    // Al retirarse/reemplazarse el archivo, no conservar una selección obsoleta.
    if (selected && !items.some(i => i.key === selected.key && i.disponible !== false)) {
      close(); selected = null;
      $('cortes').disabled = true; $('volumen').disabled = true;
      $('compatibilidad').textContent = '';
    }
    $('catalogo-estado').textContent = data.estado === 'preparando'
      ? 'Estamos preparando las series. Las opciones se actualizarán automáticamente; mientras tanto podés abrir los modelos disponibles.'
      : data.estado === 'error' ? 'No se pudieron preparar las series. Actualizá para reintentar o consultá al centro.'
      : `${data.modelos.length} modelos · ${data.series.length} series. ${data.omitidos.length ? `${data.omitidos.length} objetos del paquete no son imágenes compatibles.` : ''}`;
    if (!selected) status(items.length ? 'Seleccioná un modelo o una serie para comenzar.' : 'No hay contenido compatible disponible todavía.', 100);
    if (data.estado === 'preparando') polling = setTimeout(() => catalogo(), 5000);
    if (!selectionMade && data.seleccion && items.some(i => i.key === data.seleccion)) {
      $('contenido-selector').value = data.seleccion; select();
    }
  } catch (e) {
    if (e.name === 'AbortError') return;
    if (e.message === 'sesion') close();
    status(messages[e.message] || messages.red, 100);
  }
}
function select() {
  selectionMade = true;
  close(); selected = items.find(i => i.key === $('contenido-selector').value);
  $('cortes').disabled = selected?.kind !== 'serie'; $('volumen').disabled = !selected?.volumen;
  $('compatibilidad').textContent = selected?.motivo || (selected?.kind === 'modelo' ? 'Rotación, desplazamiento y zoom. Sin mediciones.' : '');
  if (selected) void open(selected.kind === 'modelo' ? 'modelo' : 'cortes');
}
$('contenido-selector').addEventListener('change', select);
$('cortes').onclick = () => open('cortes'); $('volumen').onclick = () => open('volumen');
$('reintentar').onclick = () => open(mode); $('actualizar').onclick = () => catalogo(true);
$('reset').onclick = () => viewer?.reset(); $('rotate').onclick = () => viewer?.rotate();
$('zoom-in').onclick = () => viewer?.zoom(.8); $('zoom-out').onclick = () => viewer?.zoom(1.25);
$('close').onclick = close;
$('fullscreen').onclick = async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.querySelector('.viewer').requestFullscreen(); } catch { status('Pantalla completa no disponible en este navegador.', 100); } };
$('slice').oninput = e => viewer?.slice(Number(e.target.value));
$('previous').onclick = () => viewer?.slice(currentSlice - 1); $('next').onclick = () => viewer?.slice(currentSlice + 1);
$('lienzo').addEventListener('wheel', e => { e.preventDefault(); if (mode === 'cortes') void viewer?.slice(currentSlice + Math.sign(e.deltaY)); }, { passive: false });
$('lienzo').addEventListener('keydown', e => { if (mode === 'cortes' && ['ArrowLeft', 'ArrowRight'].includes(e.key)) { e.preventDefault(); void viewer?.slice(currentSlice + (e.key === 'ArrowRight' ? 1 : -1)); } });
$('lienzo').addEventListener('contextmenu', e => e.preventDefault());
$('lienzo').addEventListener('webglcontextlost', e => { e.preventDefault(); close(); error('webgl'); }, true);
window.addEventListener('pagehide', () => { clearTimeout(polling); catalogController?.abort(); close(); });
void catalogo();
