import { test, expect } from '@playwright/test';

const key = 'doc_cookie_notice_v1';
const policy = '/politica-de-privacidad/';

test('aviso informativo por teclado, persistencia y cookies CSRF independientes', async ({ page, context }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#doc-cookie-notice')).toBeVisible();
  await expect(page.locator('#doc-cookie-notice')).not.toHaveAttribute('aria-modal');
  await page.getByRole('button', { name: 'Entendido', exact: true }).focus();
  expect(await page.getByRole('button', { name: 'Entendido', exact: true }).evaluate(el => getComputedStyle(el).outlineStyle)).not.toBe('none');
  await page.keyboard.press('Enter');
  await expect(page.locator('#doc-cookie-notice')).toBeHidden();
  expect(await page.evaluate(k => localStorage.getItem(k), key)).toBe('seen');
  expect((await context.cookies()).some(c => c.name === key)).toBe(false);
  const loginLink = page.locator('.landing-account');
  await loginLink.click();
  await expect(page.locator('input[name="csrfmiddlewaretoken"]')).toHaveCount(1);
  expect((await context.cookies()).some(c => c.name === 'csrftoken')).toBe(true);
  await expect(page.locator('#doc-cookie-notice')).toBeHidden();
  await page.locator('[data-privacy-footer-link]').click();
  await expect(page).toHaveURL(new RegExp(`${policy}$`));
  await page.reload();
  await expect(page.locator('#doc-cookie-notice')).toBeHidden();
  expect(errors).toEqual([]);
});

test('aviso abre política y todos los enlaces del índice tienen destino', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Ver Política de Privacidad', exact: true }).click();
  await expect(page).toHaveURL(`${'http://127.0.0.1:8767'}${policy}#cookies-utilizadas`);
  await expect(page.getByRole('heading', { name: 'Cookies', exact: true })).toBeVisible();
  expect(await page.locator('.privacy-index a').evaluateAll(links => links.every(a => document.getElementById(new URL(a.href).hash.slice(1))))).toBe(true);
  await expect(page.locator('.privacy-document section > h2')).toHaveText([
    'Introducción', 'Información que recopilamos', 'Cómo utilizamos la información',
    'Acceso a la información', 'Estudios y archivos clínicos', 'Seguridad y confidencialidad',
    'Cookies', 'Conservación de información', 'Contacto',
  ]);
  await page.getByRole('button', { name: 'Entendido', exact: true }).click();
  await page.locator('.privacy-back').click();
  await expect(page).toHaveURL('http://127.0.0.1:8767/');
});

test('almacenamiento bloqueado permite cerrar y no impide acceso ni CSRF', async ({ page, context }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => Object.defineProperty(window, 'localStorage', {
    get() { throw new DOMException('Bloqueado en prueba', 'SecurityError'); },
  }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Entendido', exact: true }).click();
  await expect(page.locator('#doc-cookie-notice')).toBeHidden();
  await page.locator('.landing-account').click();
  await expect(page.locator('#doc-cookie-notice')).toBeVisible();
  expect((await context.cookies()).some(c => c.name === 'csrftoken')).toBe(true);
  expect(errors).toEqual([]);
});

test('sin JavaScript la política y los enlaces siguen disponibles', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`http://127.0.0.1:8767${policy}`);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Política de Privacidad');
  await expect(page.locator('.doc-cookie-noscript')).toBeVisible();
  await expect(page.locator('[data-privacy-footer-link]')).toBeVisible();
  await context.close();
});

test('cerrar el aviso en una pestaña lo retira también de otra', async ({ page, context }) => {
  await page.goto('/');
  const other = await context.newPage();
  await other.goto(policy);
  await expect(other.locator('#doc-cookie-notice')).toBeVisible();
  await page.getByRole('button', { name: 'Entendido', exact: true }).click();
  await expect(other.locator('#doc-cookie-notice')).toBeHidden();
  await other.close();
});

test('revisión conjunta escritorio y móvil: lectura, foco y ausencia de desbordes', async ({ page }) => {
  const errors = [], thirdParty = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:8767/')) thirdParty.push(request.url()); });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 960 });
    await page.goto(policy);
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.locator('.privacy-back')).toBeVisible();
    const headerLayout = await page.locator('.privacy-header').evaluate(header => {
      const back = header.querySelector('.privacy-back').getBoundingClientRect();
      const account = header.querySelector('.landing-account').getBoundingClientRect();
      return { separate: back.right <= account.left || account.right <= back.left || back.bottom <= account.top || account.bottom <= back.top,
        indexSize: parseFloat(getComputedStyle(document.querySelector('.privacy-index h2')).fontSize) };
    });
    expect(headerLayout.separate).toBe(true);
    expect(headerLayout.indexSize).toBe(16);
    const notice = page.locator('#doc-cookie-notice');
    await expect(notice).toBeVisible();
    expect(await notice.evaluate(el => el.getBoundingClientRect().width <= innerWidth)).toBe(true);
    await page.screenshot({ path: `.impeccable/review/privacy-public/privacy-${width}.png`, fullPage: true });
    await page.screenshot({ path: `.impeccable/review/privacy-public/privacy-opening-${width}.png` });
    await page.getByRole('button', { name: 'Entendido', exact: true }).click();
    await expect(page.locator('#contenido')).toBeFocused();
    await page.screenshot({ path: `.impeccable/review/privacy-public/privacy-reading-${width}.png`, fullPage: true });
    await page.goto('/');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('footer').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `.impeccable/review/privacy-public/footer-${width}.png` });
    await page.evaluate(k => localStorage.removeItem(k), key);
  }
  expect(errors).toEqual([]);
  expect(thirdParty).toEqual([]);
});

test('la política impresa ocupa como máximo tres páginas A4', async ({ page }, info) => {
  await page.goto(policy);
  await page.evaluate(() => document.fonts.ready);
  const text = await page.locator('.privacy-document').innerText();
  expect(text.split(/\s+/).length).toBeLessThan(900);
  const pdf = await page.pdf({ path: '.impeccable/review/privacy-public/politica-privacidad.pdf', preferCSSPageSize: true, printBackground: true });
  const pages = (pdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length;
  expect(pages).toBeGreaterThan(0);
  expect(pages).toBeLessThanOrEqual(3);
  await info.attach('extension-impresa', { body: JSON.stringify({ words:text.split(/\s+/).length, pages }), contentType:'application/json' });
});
