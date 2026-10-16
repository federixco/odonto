/** Plan de visualización y remuestreo; nunca modifica los archivos DICOM. */
export function planParalelo(plan, budget, maxDimension, requested = 4) {
  const overhead = 8 * 1024 * 1024;
  const perImage = Math.max(1, plan.reserva_bytes - overhead);
  // Reservar explícitamente los originales/decoders simultáneos antes de
  // calcular el volumen. En equipos ajustados se reduce la concurrencia.
  const concurrency = Math.max(1, Math.min(4, requested,
    Math.floor((budget - overhead) / (perImage * 2))));
  return { concurrency, plan: adaptarPlan({ ...plan,
    reserva_bytes: overhead + perImage * concurrency }, budget, maxDimension) };
}

export function adaptarPlan(plan, budget, maxDimension = 512) {
  if (!plan || !Number.isFinite(budget) || !Number.isInteger(maxDimension) || maxDimension < 3) throw new Error('memoria');
  const source = plan.dimensiones_originales;
  if (!Array.isArray(source) || source.length !== 3 || source.some(d => !Number.isSafeInteger(d))
      || source[0] < 2 || source[1] < 2 || source[2] < 3
      || !Array.isArray(plan.espaciado_original) || plan.espaciado_original.length !== 3
      || plan.espaciado_original.some(s => !Number.isFinite(s) || s <= 0)
      || !Number.isFinite(plan.reserva_bytes) || plan.reserva_bytes < 0) throw new Error('formato');
  const available = budget - plan.reserva_bytes;
  if (available < 2 * 2 * 3 * 16) throw new Error('memoria');
  let factor = Math.max(1, Math.max(...source) / Math.min(512, maxDimension),
    Math.cbrt(source.reduce((a, b) => a * b, 1) * 16 / available));
  for (let n = 0; n < 128; n++, factor *= 1.03) {
    const dimensions = source.map((d, i) => Math.max(i === 2 ? 3 : 2, Math.ceil(d / factor)));
    const bytes = dimensions.reduce((a, b) => a * b, 1) * 4;
    if (bytes * 4 + plan.reserva_bytes > budget || Math.max(...dimensions) > maxDimension) continue;
    return { ...plan, dimensiones: dimensions, bytes,
      memoria_estimada: bytes * 4 + plan.reserva_bytes,
      espaciado: plan.espaciado_original.map((s, i) => s * (source[i] - 1) / (dimensions[i] - 1)),
      reducida: dimensions.some((d, i) => d !== source[i]),
      // Muestreo uniforme del espacio completo, incluyendo el primer y último corte.
      indices: Array.from({ length: dimensions[2] }, (_, i) => Math.round(i * (source[2] - 1) / (dimensions[2] - 1))),
    };
  }
  throw new Error('memoria');
}

export function escribirCorte(target, z, plan, image) {
  const [width, height] = plan.dimensiones_originales;
  const [outWidth, outHeight, depth] = plan.dimensiones;
  const pixels = image.getPixelData();
  if (image.columns !== width || image.rows !== height || pixels.length !== width * height
      || !Number.isInteger(z) || z < 0 || z >= depth
      || target.length !== outWidth * outHeight * depth) throw new Error('formato');
  // Cornerstone ya aplica la escala por defecto: no aplicar slope/intercept dos veces.
  const scaled = image.preScale?.scaled === true || image.isPreScaled === true;
  const slope = scaled ? 1 : (image.slope ?? 1);
  const intercept = scaled ? 0 : (image.intercept ?? 0);
  if (!Number.isFinite(slope) || !Number.isFinite(intercept)) throw new Error('formato');
  let offset = z * outWidth * outHeight;
  for (let y = 0; y < outHeight; y++) {
    const sy = y * (height - 1) / (outHeight - 1), y0 = Math.floor(sy), y1 = Math.min(height - 1, y0 + 1), fy = sy - y0;
    for (let x = 0; x < outWidth; x++) {
      const sx = x * (width - 1) / (outWidth - 1), x0 = Math.floor(sx), x1 = Math.min(width - 1, x0 + 1), fx = sx - x0;
      const top = pixels[y0 * width + x0] * (1 - fx) + pixels[y0 * width + x1] * fx;
      const bottom = pixels[y1 * width + x0] * (1 - fx) + pixels[y1 * width + x1] * fx;
      const value = (top * (1 - fy) + bottom * fy) * slope + intercept;
      if (!Number.isFinite(value) || Math.abs(value) > 3.4028234663852886e38) throw new Error('formato');
      target[offset++] = value;
    }
  }
}
