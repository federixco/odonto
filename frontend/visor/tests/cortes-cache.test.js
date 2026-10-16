import test from 'node:test';
import assert from 'node:assert/strict';
import { CacheCortes, cargarEnParalelo } from '../cortes-cache.js';
import { planParalelo } from '../volumen.js';

const tick = () => new Promise(resolve => setImmediate(resolve));
const waitFor = async condition => {
  for (let i = 0; i < 100; i++) { if (condition()) return; await tick(); }
  assert.fail('No terminó la cola');
};
function fixture(options = {}) {
  const calls = [], released = [];
  const cache = new CacheCortes({ costs: Array(20).fill(10), budget: 200, concurrency: 4,
    load: async index => { calls.push(index); await tick(); return { index }; },
    release: index => released.push(index), ...options });
  return { cache, calls, released };
}

test('120 → 121 → 120 reutiliza caché, deduplica solicitudes y libera al cerrar', async () => {
  const { cache, calls } = fixture({ costs: Array(150).fill(10), budget: 300 });
  cache.protect([119]);
  const first = cache.get(119);
  assert.equal(first, cache.get(119));
  await first;
  cache.prefetch(119);
  await waitFor(() => cache.active === 0);
  cache.protect([119, 120]);
  await cache.get(120);
  assert.equal((await cache.get(119)).index, 119);
  assert.equal(calls.filter(i => i === 119).length, 1);
  assert.equal(calls.filter(i => i === 120).length, 1);
  cache.dispose();
  assert.equal(cache.bytes, 0);
  await assert.rejects(cache.get(119), { name: 'AbortError' });
});

test('precarga completa si entra; ventana y RAM acotadas si no entra', async () => {
  const { cache, calls } = fixture({ budget: 400 });
  cache.prefetch(0);
  await waitFor(() => cache.active === 0);
  assert.equal(calls.length, 20);
  cache.dispose();
  const second = fixture({ budget: 60 });
  second.cache.protect([0]);
  await second.cache.get(0);
  second.cache.prefetch(0);
  await waitFor(() => second.cache.active === 0);
  assert.ok(second.calls.length < 20);
  second.cache.protect([0, 18]);
  await second.cache.get(18);
  second.cache.protect([18]);
  second.cache.prefetch(18);
  await waitFor(() => second.cache.active === 0);
  assert.ok(second.cache.bytes <= 60);
  assert.ok(second.released.length > 0);
  assert.equal((await second.cache.get(18)).index, 18);
  second.cache.dispose();
});

test('salto manual tiene prioridad sobre nuevas precargas y respeta concurrencia', async () => {
  const releases = [], order = [];
  const { cache } = fixture({ concurrency: 2, budget: 400,
    load: index => new Promise(resolve => { order.push(index); releases.push(() => resolve(index)); }) });
  cache.prefetch(0);
  assert.deepEqual(order, [0, 1]);
  const jump = cache.get(19);
  releases.shift()(); await tick();
  assert.deepEqual(order, [0, 1, 19]);
  cache.dispose();
  await assert.rejects(jump, { name: 'AbortError' });
  for (const release of releases) release();
  await tick();
  assert.equal(cache.bytes, 0);
});

test('precarga fallida no se repite sin fin y se reintenta por demanda', async () => {
  let count = 0;
  const { cache } = fixture({ costs: [10], load: async () => { if (++count === 1) throw new Error('red'); return 'ok'; } });
  cache.prefetch(0);
  await waitFor(() => cache.active === 0);
  cache.prefetch(0); await tick();
  assert.equal(count, 1);
  assert.equal(await cache.get(0), 'ok');
  cache.dispose();
});

test('no espera indefinidamente cuando imágenes protegidas agotan el presupuesto', async () => {
  const { cache } = fixture({ budget: 10 });
  cache.protect([0, 1]); await cache.get(0);
  await assert.rejects(cache.get(1), /memoria/);
  cache.dispose();
});

test('volumen paralelo escribe por índice, tiene concurrencia limitada y propaga fallos', async () => {
  let active = 0, peak = 0;
  const written = [];
  const controller = new AbortController();
  await cargarEnParalelo(16, 4, controller.signal, async index => {
    peak = Math.max(peak, ++active);
    await tick(); written[index] = index; active--;
  });
  assert.equal(peak, 4);
  assert.deepEqual(written, Array.from({ length: 16 }, (_, i) => i));
  let started = 0;
  await assert.rejects(cargarEnParalelo(30, 4, controller.signal, async () => {
    started++; throw new Error('red');
  }), /red/);
  assert.equal(started, 4);
  controller.abort();
  await assert.rejects(cargarEnParalelo(16, 4, controller.signal, async () => assert.fail()), { name: 'AbortError' });
});

test('el plan 3D reserva RAM para todas las cargas simultáneas, sin aumentar el límite', () => {
  const MiB = 1024 * 1024;
  const input = { dimensiones_originales: [640, 640, 640], espaciado_original: [.2, .2, .2], reserva_bytes: 16 * MiB };
  const { concurrency, plan } = planParalelo(input, 256 * MiB, 512, 4);
  assert.equal(concurrency, 4);
  assert.equal(plan.reserva_bytes, 40 * MiB);
  assert.ok(plan.memoria_estimada <= 256 * MiB);
  assert.equal(plan.indices.at(-1), 639);
  assert.equal(planParalelo(input, 32 * MiB, 128, 4).concurrency, 1);
});
