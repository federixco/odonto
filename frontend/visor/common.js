/** Transferencia acotada con URL del sistema: cookie solo al mismo origen. */
export async function descargar(url, { signal, maxBytes, progress = () => {} }) {
  const response = await fetch(url, { signal, credentials: 'same-origin', cache: 'no-store', referrerPolicy: 'no-referrer' });
  if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'sesion' : 'red');
  const total = Number(response.headers.get('Content-Length')) || 0;
  if (total > maxBytes) { await response.body?.cancel(); throw new Error('memoria'); }
  const reader = response.body.getReader();
  const partes = [];
  let loaded = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      loaded += value.byteLength;
      if (loaded > maxBytes) throw new Error('memoria');
      partes.push(value);
      progress(total ? Math.min(99, Math.round(loaded / total * 100)) : null);
    }
  } finally { await reader.cancel().catch(() => {}); }
  const buffer = new Uint8Array(loaded);
  let offset = 0;
  for (const parte of partes) { buffer.set(parte, offset); offset += parte.byteLength; }
  return buffer.buffer;
}

export function comprobarWebGL() {
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl2');
  if (!gl) throw new Error('webgl');
  gl.getExtension('WEBGL_lose_context')?.loseContext();
}

export async function json(url, options = {}) {
  const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
  if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'sesion' : 'red');
  return response.json();
}
