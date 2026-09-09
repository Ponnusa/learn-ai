import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    lib: {
      entry: 'src/content/selectionPill.ts',
      name: 'genieContent',
      formats: ['iife'],
      fileName: () => 'content.js',
    },
  },
});
