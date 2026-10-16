/** Cierra únicamente el servidor de páginas públicas de esta ejecución. */
export default async function teardown() {
  await fetch('http://127.0.0.1:8767/__test_shutdown', {
    method: 'POST', headers: { 'X-Test-Token': process.env.DOC_PUBLIC_TEST_TOKEN },
    signal: AbortSignal.timeout(3000),
  });
  for (let n = 0; n < 30; n++) {
    try { await fetch('http://127.0.0.1:8767/', { signal: AbortSignal.timeout(300) }); }
    catch { return; }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('El servidor público de pruebas no terminó de cerrarse.');
}
