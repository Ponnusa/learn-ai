import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Builds the side panel as a normal Vite React SPA (esm, code-split fine —
// it's just a regular web page loaded via manifest.json's side_panel).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: false, // vite.ext.config.ts writes background.js/content.js into the same dist/
    rollupOptions: {
      input: { panel: 'panel.html' },
    },
  },
});
