/** Cierra SOLO el servidor sintético de esta ejecución, también en Windows. */
export default async function teardown() {
  if (process.env.VISOR_TEST_EXTERNAL_SERVER === '1') return;
  await fetch('http://127.0.0.1:8765/__test_shutdown', {
    method: 'POST', headers: { 'X-Test-Token': process.env.VISOR_FIXTURE_TOKEN },
    signal: AbortSignal.timeout(3000),
  });
  // Playwright puede intentar taskkill antes de que el servidor cierre su socket.
  for (let n = 0; n < 30; n++) {
    try { await fetch('http://127.0.0.1:8765/diagnostico', { signal: AbortSignal.timeout(200) }); }
    catch { return; }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('El servidor sintético no terminó de cerrarse.');
}
