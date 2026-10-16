/** Caché de una apertura: RAM acotada, cola prioritaria y precarga por proximidad.
 * El costo incluye originales, píxeles y buffers temporales; no solo la descarga.
 * No persiste imágenes ni URLs en disco/localStorage.
 */
export class CacheCortes {
  constructor({ costs, budget, concurrency, load, release, onError = () => {} }) {
    this.costs = costs;
    this.budget = budget;
    this.concurrency = Math.max(1, Math.min(4, concurrency));
    this.load = load;
    this.release = release;
    this.onError = onError;
    this.entries = new Map();
    this.wanted = [];
    this.pinned = new Set();
    this.failed = new Set();
    this.bytes = 0;
    this.active = 0;
    this.clock = 0;
    this.closed = false;
  }

  protect(indices) { this.pinned = new Set(indices); }

  get(index) {
    if (this.closed) return Promise.reject(new DOMException('Cancelado', 'AbortError'));
    const cost = this.costs[index];
    if (!Number.isFinite(cost) || cost <= 0 || cost > this.budget) return Promise.reject(new Error('memoria'));
    let entry = this.entries.get(index);
    if (!entry) {
      entry = { index, cost, state: 'queued', used: ++this.clock };
      entry.promise = new Promise((resolve, reject) => { entry.resolve = resolve; entry.reject = reject; });
      // La precarga no tiene consumidor; sus fallos se notifican por onError.
      entry.promise.catch(() => {});
      this.entries.set(index, entry);
    }
    entry.demand = true;
    entry.used = ++this.clock;
    this.pump();
    return entry.promise;
  }

  prefetch(center) {
    if (this.closed) return;
    this.wanted = [];
    // Dejar margen para solicitudes en vuelo y para saltar a otro corte.
    let available = this.budget * .7;
    for (let distance = 0; distance < this.costs.length; distance++) {
      for (const index of distance ? [center + distance, center - distance] : [center]) {
        if (index < 0 || index >= this.costs.length) continue;
        if (this.costs[index] <= available) {
          this.wanted.push(index);
          available -= this.costs[index];
        }
      }
    }
    this.pump();
  }

  room(cost, demand) {
    while (this.bytes + cost > this.budget) {
      const candidates = [...this.entries.values()].filter(e => e.state === 'ready'
        && !this.pinned.has(e.index) && (demand || !this.wanted.includes(e.index)));
      candidates.sort((a, b) => a.used - b.used);
      if (!candidates.length) return false;
      const entry = candidates[0];
      this.entries.delete(entry.index);
      this.bytes -= entry.cost;
      this.release(entry.index);
    }
    return true;
  }

  pump() {
    if (this.closed) return;
    while (this.active < this.concurrency) {
      let entry = [...this.entries.values()].find(e => e.state === 'queued' && e.demand);
      if (!entry) {
        const index = this.wanted.find(i => !this.entries.has(i) && !this.failed.has(i));
        if (index === undefined) return;
        entry = { index, cost: this.costs[index], state: 'queued', demand: false, used: ++this.clock };
        entry.promise = new Promise((resolve, reject) => { entry.resolve = resolve; entry.reject = reject; });
        entry.promise.catch(() => {});
      }
      if (!this.room(entry.cost, entry.demand)) {
        // Una petición explícita no puede quedar esperando si nada liberará RAM.
        if (entry.demand && !this.active) {
          this.entries.delete(entry.index);
          entry.reject(new Error('memoria'));
        }
        return;
      }
      this.entries.set(entry.index, entry);
      entry.state = 'loading';
      this.bytes += entry.cost;
      this.active++;
      void this.run(entry);
    }
  }

  async run(entry) {
    try {
      const image = await this.load(entry.index);
      if (this.closed) return;
      entry.state = 'ready';
      entry.used = ++this.clock;
      entry.resolve(image);
    } catch (error) {
      if (!this.closed) {
        this.entries.delete(entry.index);
        this.bytes -= entry.cost;
        this.release(entry.index);
        this.failed.add(entry.index); // No reintentar en bucle una precarga fallida.
        entry.reject(error);
        this.onError(error);
      }
    } finally {
      this.active--;
      if (!this.closed) this.pump();
    }
  }

  dispose() {
    if (this.closed) return;
    this.closed = true;
    for (const entry of this.entries.values()) {
      entry.reject(new DOMException('Cancelado', 'AbortError'));
      this.release(entry.index);
    }
    this.entries.clear();
    this.wanted = [];
    this.bytes = 0;
  }
}

/** No genera una promesa por corte ni acumula imágenes completadas fuera de orden. */
export async function cargarEnParalelo(count, concurrency, signal, task) {
  let next = 0, failure;
  const workers = Array.from({ length: Math.min(count, concurrency) }, async () => {
    while (!failure && !signal.aborted) {
      const index = next++;
      if (index >= count) return;
      try { await task(index); }
      catch (error) { failure ||= error; throw error; }
    }
  });
  await Promise.all(workers);
  signal.throwIfAborted();
}
