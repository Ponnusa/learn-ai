import { defineConfig } from 'vite';

// Rollup refuses "iife" output for a multi-entry build even when the entries
// share no code (it validates multi-chunk output generically) — so the
// background worker and content script each get their own single-entry
// config rather than one shared vite.ext.config.ts.
export default defineConfig({
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    lib: {
      entry: 'src/background/index.ts',
      name: 'genieBackground',
      formats: ['iife'],
      fileName: () => 'background.js',
    },
  },
});
