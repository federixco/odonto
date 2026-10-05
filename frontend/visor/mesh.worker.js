import { parseMesh } from './mesh-parser.js';

// Parsear fuera del hilo de interfaz; cerrar/cambiar termina este worker.
self.onmessage = ({ data }) => {
  try {
    const { geometry, faces } = parseMesh(data.buffer, data.formato, data.limits);
    const attributes = {};
    const transfers = [];
    for (const name of ['position', 'normal', 'color']) {
      const a = geometry.getAttribute(name);
      if (a) { attributes[name] = { array: a.array, itemSize: a.itemSize, normalized: a.normalized }; transfers.push(a.array.buffer); }
    }
    const index = geometry.index?.array;
    if (index) transfers.push(index.buffer);
    self.postMessage({ attributes, index, faces }, transfers);
    geometry.dispose();
  } catch (e) { self.postMessage({ error: ['memoria', 'formato'].includes(e.message) ? e.message : 'formato' }); }
};
