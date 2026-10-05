import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve('.local/pw-browsers');
process.env.VISOR_FIXTURE_TOKEN ||= randomUUID();

export default defineConfig({
  testDir: 'frontend/visor/browser-tests',
  timeout: 60000,
  workers: 1,
  globalTeardown: './frontend/visor/browser-tests/teardown.js',
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    ...(process.env.VISOR_BROWSER_MATRIX === '1' ? [
      { name:'chrome', use:{ browserName:'chromium', channel:'chrome' } },
      { name:'edge', use:{ browserName:'chromium', channel:'msedge' } },
      { name:'firefox', use:{ browserName:'firefox', launchOptions:{ timeout:20000, args:[], firefoxUserPrefs:{ 'webgl.force-enabled':true } } } },
    ] : []),
  ],
  use: { baseURL: 'http://127.0.0.1:8765', viewport: { width: 1365, height: 900 },
    launchOptions: { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
    screenshot: 'only-on-failure', trace: 'retain-on-failure',
  },
  webServer: process.env.VISOR_TEST_EXTERNAL_SERVER === '1' ? undefined : {
    command: process.platform === 'win32' ? '.venv\\Scripts\\python.exe -m tests.visor_browser_server' : '.venv/bin/python -m tests.visor_browser_server',
    url: 'http://127.0.0.1:8765', reuseExistingServer: false,
  },
});
