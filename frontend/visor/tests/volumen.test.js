import test from 'node:test';
import assert from 'node:assert/strict';
import { adaptarPlan, escribirCorte } from '../volumen.js';

const MiB = 1024 * 1024;
const sourcePlan = (dimensions = [512, 512, 200]) => ({
  dimensiones_originales: dimensions, espaciado_original: [.4, .6, 1.2],
  origen: [10, 20, 30], direccion: [1, 0, 0, 0, 1, 0, 0, 0, 1], reserva_bytes: 14 * MiB,
});

test('una serie de más de 800 MiB estimados cabe en 256 MiB como vista 3D', () => {
  const plan = adaptarPlan(sourcePlan(), 256 * MiB);
  assert.equal(plan.reducida, true);
  assert.ok(plan.memoria_estimada <= 256 * MiB);
  assert.equal(plan.indices[0], 0);
  assert.equal(plan.indices.at(-1), 199);
  assert.equal(new Set(plan.indices).size, plan.indices.length);
  plan.espaciado.forEach((spacing, i) => {
    assert.ok(Math.abs(spacing * (plan.dimensiones[i] - 1)
      - plan.espaciado_original[i] * (plan.dimensiones_originales[i] - 1)) < 1e-8);
  });
});

test('presupuestos menores y límite de textura GPU reducen más, no cargan originales completos', () => {
  const small = adaptarPlan(sourcePlan(), 64 * MiB, 128);
  assert.ok(small.dimensiones.every(d => d <= 128));
  assert.ok(small.memoria_estimada <= 64 * MiB);
  assert.throws(() => adaptarPlan(sourcePlan(), 1000), /memoria/);
});

test('una serie pequeña conserva todos los cortes y su resolución', () => {
  const plan = adaptarPlan(sourcePlan([64, 64, 16]), 256 * MiB);
  assert.equal(plan.reducida, false);
  assert.deepEqual(plan.indices, Array.from({ length: 16 }, (_, i) => i));
});

test('interpolación XY, extremos físicos y escala aplicada una sola vez', () => {
  const plan = { dimensiones_originales: [4, 4, 3], dimensiones: [3, 3, 3] };
  const image = { columns: 4, rows: 4, slope: 2, intercept: -1000,
    getPixelData: () => Int16Array.from({ length: 16 }, (_, i) => i) };
  const data = new Float32Array(27);
  escribirCorte(data, 0, plan, image);
  assert.equal(data[0], -1000);
  assert.equal(data[4], -985);
  assert.equal(data[8], -970);
  image.preScale = { scaled: true };
  escribirCorte(data, 1, plan, image);
  assert.equal(data[13], 7.5);
});

test('rechaza tamaños, números o píxeles inválidos antes de presentar el volumen', () => {
  assert.throws(() => adaptarPlan(sourcePlan([NaN, 512, 200]), 256 * MiB), /formato/);
  const plan = { dimensiones_originales: [2, 2, 3], dimensiones: [2, 2, 3] };
  const image = { columns: 2, rows: 2, getPixelData: () => [0, 0, NaN, 0] };
  assert.throws(() => escribirCorte(new Float32Array(12), 0, plan, image), /formato/);
  assert.throws(() => escribirCorte(new Float32Array(1), 0, plan, image), /formato/);
  image.getPixelData = () => [1e200, 1e200, 1e200, 1e200];
  assert.throws(() => escribirCorte(new Float32Array(12), 0, plan, image), /formato/);
});
