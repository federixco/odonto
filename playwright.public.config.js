import { defineConfig } from '@playwright/test';
import { randomUUID } from 'node:crypto';

process.env.DOC_PUBLIC_TEST_TOKEN ||= randomUUID();

export default defineConfig({
  testDir: 'frontend/public/browser-tests',
  timeout: 30000,
  workers: 1,
  globalTeardown: './frontend/public/browser-tests/teardown.js',
  use: {
    baseURL: 'http://127.0.0.1:8767',
    browserName: 'chromium', channel: process.env.DOC_PUBLIC_BROWSER_CHANNEL || 'msedge',
    headless: true, viewport: { width: 1440, height: 960 },
    trace: 'retain-on-failure', screenshot: 'only-on-failure',
  },
  webServer: {
    command: process.platform === 'win32'
      ? '.venv\\Scripts\\python.exe -m tests.public_browser_server'
      : '.venv/bin/python -m tests.public_browser_server',
    url: 'http://127.0.0.1:8767', reuseExistingServer: false,
  },
});
