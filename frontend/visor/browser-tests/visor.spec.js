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
  await page.route('**/archivos/100/contenido/', async route => {
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
  await page.route('**/archivos/1/contenido/', route => route.fulfill({ status:503, body:'Temporalmente no disponible' }));
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
  await page.goto('/?archivo=100');
  await expect(page.locator('#contenido-selector')).toHaveValue('s-sintetica');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  let started;
  const waiting = new Promise(resolve => { started=resolve; });
  await page.route('**/archivos/101/contenido/', async route => {
    started();
    await new Promise(r=>setTimeout(r,500));
    await route.continue().catch(()=>{});
  });
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
  await page.goto('/?archivo=100');
  await expect(page.locator('#estado')).toContainText('Cortes listos');
  await page.route('**/archivos/101/contenido/', route => route.fulfill({ status:403, body:'No autorizado' }));
  await page.locator('#next').click();
  await expect(page.locator('#estado')).toContainText('permiso ya no están vigentes');
  await expect(page.locator('#lienzo canvas')).toHaveCount(0);
  await expect(page.locator('#reintentar')).toBeHidden();
});
