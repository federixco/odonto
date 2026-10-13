import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// Solo compilación: Django/Nginx sirven este directorio tras collectstatic.
export default defineConfig({
  base: './',
  resolve: { alias: { events: 'events/' } },
  build: {
    outDir: 'static/visor/dist', emptyOutDir: true, sourcemap: false,
    assetsInlineLimit: 0,
    rolldownOptions: {
      input: resolve('frontend/visor/main.js'),
      output: {
        entryFileNames: 'visor.js',
        chunkFileNames: '[name]-[hash].js',
        assetFileNames: (asset) => asset.names?.some(n => n.endsWith('.css')) ? 'visor.css' : '[name]-[hash][extname]',
      },
    },
  },
  worker: { format: 'es' },
});
