import { test, expect } from '@playwright/test';

test('STL y PLY reales en WebGL, cierre, reapertura y vista pequeña', async ({ page }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  for (const key of ['m-1', 'm-2', 'm-1']) {
    await page.locator('#contenido-selector').selectOption(key);
    await expect(page.locator('#estado')).toContainText('Modelo listo', { timeout: 30000 });
    await expect(page.locator('#lienzo canvas')).toHaveCount(1);
    await page.locator('#rotate').click(); await page.locator('#zoom-in').click(); await page.locator('#reset').click();
    await page.screenshot({ path: `test-results/${key}-modelo.png` });
    await page.locator('#close').click();
    await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  }
  await page.setViewportSize({ width:390, height:844 });
  await page.locator('#contenido-selector').selectOption('m-2');
  await expect(page.locator('#estado')).toContainText('Modelo listo');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('DICOM cortes y volumen real con redirección privada, sin cookies en S3', async ({ page, request }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.locator('#contenido-selector').selectOption('s-sintetica');
  await expect(page.locator('#estado')).toContainText('Cortes listos', { timeout:30000 });
  await page.locator('#next').click();
  await expect(page.locator('#slice-value')).toContainText('2 / 16');
  await page.screenshot({ path:'test-results/dicom-cortes.png' });
  await page.locator('#volumen').click();
  await expect(page.locator('#estado')).toContainText('Volumen listo', { timeout:45000 });
  await page.locator('#rotate').click(); await page.locator('#reset').click();
  await page.screenshot({ path:'test-results/dicom-volumen.png' });
  await page.locator('#close').click();
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  await expect.poll(() => page.workers().length).toBe(0);
  await page.locator('#cortes').click();
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  const diag = await (await request.get('/diagnostico')).json();
  expect(diag.lecturas.some(x => x.id >= 100)).toBe(true);
  expect(diag.lecturas.every(x => !x.cookie)).toBe(true);
  expect(errors).toEqual([]);
});

test('cancelar una serie que está cargando no monta una vista tardía', async ({ page }) => {
  const errors=[]; page.on('pageerror', e=>errors.push(e.message));
  await page.goto('/');
  let started;
  const waiting = new Promise(resolve => { started=resolve; });
  await page.route('**/archivos/100/contenido/**', async route => {
    started();
    await new Promise(r => setTimeout(r,500));
    await route.continue().catch(()=>{});
  });
  await page.locator('#contenido-selector').selectOption('s-sintetica');
  await waiting;
  await page.locator('#close').click();
  await page.locator('#contenido-selector').selectOption('m-2');
  await expect(page.locator('#estado')).toContainText('Modelo listo');
  await expect(page.locator('#lienzo canvas')).toHaveCount(1);
  await expect.poll(()=>page.workers().length).toBe(0);
  expect(errors).toEqual([]);
});

test('red, cancelación y falta de WebGL muestran error controlado', async ({ page }) => {
  await page.goto('/');
  await page.route('**/archivos/1/contenido/**', route => route.fulfill({ status:503, body:'Temporalmente no disponible' }));
  await page.locator('#contenido-selector').selectOption('m-1');
  await expect(page.locator('#estado')).toContainText('No se pudo cargar');
  await page.unrouteAll();
  await page.locator('#reintentar').click();
  await expect(page.locator('#estado')).toContainText('Modelo listo');
  await page.locator('#close').click();
  await page.evaluate(() => { HTMLCanvasElement.prototype.getContext = () => null; });
  await page.locator('#contenido-selector').selectOption('m-2');
  await expect(page.locator('#estado')).toContainText('WebGL 2');
});

test('tres aperturas de volumen liberan workers y no acumulan heap sin límite', async ({ page, browserName }, info) => {
  test.skip(browserName !== 'chromium', 'La medición CDP solo existe en Chromium.');
  const cdp = await page.context().newCDPSession(page);
  const medidas=[];
  await page.goto('/');
  await page.locator('#contenido-selector').selectOption('s-sintetica');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  for (let n=0; n<3; n++) {
    const inicio=Date.now();
    await page.locator('#volumen').click();
    await expect(page.locator('#estado')).toContainText('Volumen listo', {timeout:30000});
    const abierto=await cdp.send('Runtime.getHeapUsage');
    await page.locator('#close').click();
    await expect.poll(()=>page.workers().length).toBe(0);
    await cdp.send('HeapProfiler.collectGarbage');
    const cerrado=await cdp.send('Runtime.getHeapUsage');
    medidas.push({ ms:Date.now()-inicio, abierto, cerrado });
  }
  await info.attach('memoria-sintetica', { body:JSON.stringify({ medidas, agente:await page.evaluate(()=>navigator.userAgent) }, null,2), contentType:'application/json' });
  // Tolerancia de cachés JS del motor: no equivale a una medición de memoria GPU.
  expect(medidas[2].cerrado.usedSize - medidas[0].cerrado.usedSize).toBeLessThan(20*1024*1024);
});

test('el enlace directo DICOM abre su serie y el deslizador respeta el último corte', async ({ page }) => {
  const errors=[]; page.on('pageerror', e=>errors.push(e.message));
  let started;
  const waiting = new Promise(resolve => { started=resolve; });
  await page.route('**/archivos/101/contenido/**', async route => {
    started();
    await new Promise(r=>setTimeout(r,500));
    await route.continue().catch(()=>{});
  });
  await page.goto('/?archivo=100');
  await expect(page.locator('#contenido-selector')).toHaveValue('s-sintetica');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await page.locator('#next').click();
  await waiting;
  await page.locator('#slice').evaluate(element=>{
    for (const value of ['5','9','16']) {
      element.value=value; element.dispatchEvent(new Event('input',{bubbles:true}));
    }
  });
  await expect(page.locator('#slice-value')).toHaveText('16 / 16');
  await expect(page.locator('#slice')).toHaveValue('16');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  expect(errors).toEqual([]);
});

test('multiframe cambia píxeles entre frames y RLE se decodifica en cortes y volumen', async ({ page }) => {
  const errors=[]; page.on('pageerror', e=>errors.push(e.message));
  let lecturasMultiframe=0;
  page.on('request', request=>{ if (new URL(request.url()).pathname.endsWith('/archivos/200/contenido/')) lecturasMultiframe++; });
  await page.goto('/?archivo=200');
  await expect(page.locator('#estado')).toContainText('Cortes listos', {timeout:30000});
  await expect(page.locator('#volumen')).toBeDisabled();
  const primero = await page.locator('#lienzo').screenshot();
  await page.locator('#slice').fill('3');
  await expect(page.locator('#slice-value')).toHaveText('3 / 3');
  const tercero = await page.locator('#lienzo').screenshot();
  expect(primero.equals(tercero)).toBe(false);
  await page.locator('#previous').click();
  await expect(page.locator('#slice-value')).toHaveText('2 / 3');
  expect(lecturasMultiframe).toBe(1);
  await page.locator('#contenido-selector').selectOption('s-rle');
  await expect(page.locator('#estado')).toContainText('Cortes listos', {timeout:30000});
  await page.locator('#volumen').click();
  await expect(page.locator('#estado')).toContainText('Volumen listo', {timeout:30000});
  await page.locator('#close').click();
  await expect.poll(()=>page.workers().length).toBe(0);
  expect(errors).toEqual([]);
});

test('actualizar catálogo retira una selección que ya no está disponible', async ({ page }) => {
  await page.goto('/?archivo=1');
  await expect(page.locator('#estado')).toContainText('Modelo listo');
  await page.route('**/catalogo/**', route=>route.fulfill({
    json:{ estado:'listo', modelos:[], series:[], omitidos:[], seleccion:null },
  }));
  await page.locator('#actualizar').click();
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  await expect(page.locator('#reset')).toBeDisabled();
  await expect(page.locator('#contenido-selector')).toHaveValue('');
});

test('permiso revocado durante la navegación cierra la imagen anterior', async ({ page }) => {
  let revoke;
  const revoked = new Promise(resolve => { revoke = resolve; });
  await page.route('**/archivos/101/contenido/**', async route => {
    await revoked;
    await route.fulfill({ status:403, body:'No autorizado' }).catch(() => {});
  });
  await page.goto('/?archivo=100');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await page.locator('#next').click();
  revoke();
  await expect(page.locator('#estado')).toContainText('permiso ya no están vigentes');
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  await expect(page.locator('#reintentar')).toBeHidden();
});

test('serie pesada reconstruye 3D adaptado, descarga paralela acotada y vuelve a cortes originales', async ({ page, request }, info) => {
  test.setTimeout(120000);
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  let active = 0, peak = 0;
  const large = request => /\/archivos\/4\d\d\/contenido\/$/.test(new URL(request.url()).pathname);
  page.on('request', request => { if (large(request)) { active++; peak = Math.max(peak, active); } });
  page.on('requestfinished', request => { if (large(request)) active--; });
  page.on('requestfailed', request => { if (large(request)) active--; });
  await page.goto('/?archivo=400');
  await expect(page.locator('#estado')).toContainText('Cortes listos', { timeout:30000 });
  await expect(page.locator('#volumen')).toBeEnabled();
  const serie = await (await request.get('/estudios/1/visor/series/grande/')).json();
  expect(serie.vista_3d.reducida).toBe(true);
  expect(serie.vista_3d.memoria_estimada).toBeLessThanOrEqual(256 * 1024 * 1024);
  await expect.poll(() => active).toBe(0);
  peak = 0;
  await page.locator('#volumen').click();
  await expect(page.locator('#estado')).toContainText('Volumen listo', { timeout:90000 });
  await expect(page.locator('#compatibilidad')).toContainText('resolución adaptada');
  await expect(page.locator('#lienzo canvas')).toHaveCount(1);
  await page.locator('#rotate').click(); await page.locator('#zoom-in').click();
  await info.attach('volumen-grande-adaptado', { body:await page.locator('#lienzo').screenshot(), contentType:'image/png' });
  expect(peak).toBeGreaterThan(1);
  expect(peak).toBeLessThanOrEqual(4);
  await page.locator('#cortes').click();
  await expect(page.locator('#estado')).toContainText('Cortes listos', { timeout:30000 });
  await expect(page.locator('#slice-value')).toHaveText('1 / 80');
  await page.locator('#slice').fill('80');
  await expect(page.locator('#slice-value')).toHaveText('80 / 80');
  await page.locator('#close').click();
  await expect.poll(() => page.workers().length).toBe(0);
  expect(errors).toEqual([]);
});

test('un fallo al construir la vista 3D no presenta un volumen incompleto', async ({ page }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/?archivo=100');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await page.route('**/archivos/105/contenido/**', route => route.fulfill({ status:503, body:'Prueba de fallo' }));
  await page.locator('#volumen').click();
  await expect(page.locator('#estado')).toContainText('No se pudo cargar', { timeout:30000 });
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  await expect.poll(() => page.workers().length).toBe(0);
  await page.unrouteAll();
  await page.locator('#reintentar').click();
  await expect(page.locator('#estado')).toContainText('Volumen listo', { timeout:30000 });
  expect(errors).toEqual([]);
});

test('2D precarga la serie pequeña y volver a un corte no hace otra descarga', async ({ page }, info) => {
  const reads = new Map(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', request => {
    const match = new URL(request.url()).pathname.match(/\/archivos\/(1\d\d)\/contenido\//);
    if (match) reads.set(match[1], (reads.get(match[1]) || 0) + 1);
  });
  await page.route('**/archivos/*/contenido/**', async route => {
    await new Promise(resolve => setTimeout(resolve, 150));
    await route.continue().catch(() => {});
  });
  await page.goto('/?archivo=100');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await expect.poll(() => reads.size).toBe(16);
  await page.locator('#slice').fill('12');
  await expect(page.locator('#slice-value')).toHaveText('12 / 16');
  await page.locator('#next').click();
  await expect(page.locator('#slice-value')).toHaveText('13 / 16');
  const started = Date.now();
  await page.locator('#previous').click();
  await expect(page.locator('#slice-value')).toHaveText('12 / 16');
  await info.attach('cache-2d', { body: JSON.stringify({ volverMs: Date.now() - started, lecturas: Object.fromEntries(reads) }), contentType: 'application/json' });
  expect([...reads.values()].every(count => count === 1)).toBe(true);
  expect(errors).toEqual([]);
});

test('revocación se comprueba aun cuando toda la serie ya está en caché', async ({ page }) => {
  await page.clock.install();
  await page.goto('/?archivo=100');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await page.route('**/series/sintetica/', route => route.fulfill({ status:403, body:'Revocado' }));
  await page.clock.fastForward(31000);
  await expect(page.locator('#estado')).toContainText('permiso ya no están vigentes');
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
});

test('3D completa con latencia, carga en paralelo y cancelación corta nuevas solicitudes', async ({ page }, info) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  let active = 0, peak = 0, count = 0;
  await page.route('**/archivos/*/contenido/**', async route => {
    count++; active++; peak = Math.max(peak, active);
    await new Promise(resolve => setTimeout(resolve, 200));
    active--;
    await route.continue().catch(() => {});
  });
  await page.goto('/?archivo=100');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await expect.poll(() => count).toBe(16);
  await expect.poll(() => active).toBe(0);
  peak = 0; count = 0;
  const started = Date.now();
  await page.locator('#volumen').click();
  await expect(page.locator('#estado')).toContainText('Volumen listo', { timeout:30000 });
  await info.attach('carga-3d-con-latencia', { body: JSON.stringify({ ms:Date.now()-started, peak, count }), contentType:'application/json' });
  expect(peak).toBeGreaterThan(1);
  expect(peak).toBeLessThanOrEqual(4);
  expect(count).toBe(16);
  await page.locator('#volumen').click();
  await expect.poll(() => active).toBeGreaterThan(0);
  await page.locator('#close').click();
  const afterClose = count;
  await expect.poll(() => page.workers().length).toBe(0);
  await expect.poll(() => active).toBe(0);
  expect(count).toBe(afterClose);
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('un corte 3D que no responde termina en error y permite reintentar', async ({ page }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/?archivo=100');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await page.clock.install();
  let unblock, started;
  const stalled = new Promise(resolve => { started = resolve; });
  const blocked = new Promise(resolve => { unblock = resolve; });
  await page.route('**/archivos/105/contenido/**', async route => {
    started(); await blocked; await route.continue().catch(() => {});
  });
  await page.locator('#volumen').click();
  await stalled;
  await page.clock.fastForward(61000);
  await expect(page.locator('#estado')).toContainText('No se pudo cargar');
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  await expect(page.locator('#reintentar')).toBeVisible();
  unblock();
  await page.unrouteAll({ behavior: 'wait' });
  await page.locator('#reintentar').click();
  await expect(page.locator('#estado')).toContainText('Volumen listo');
  expect(errors).toEqual([]);
});
