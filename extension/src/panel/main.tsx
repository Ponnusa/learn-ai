import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '../styles/theme.css';
import 'katex/dist/katex.min.css';

// No persisted user theme preference to read in the panel (unlike the main
// app, which stores one) — just follow the OS, same as the app's dark
// default/fallback convention.
const isLight = window.matchMedia('(prefers-color-scheme: light)').matches;
document.documentElement.dataset.theme = isLight ? 'light' : 'dark';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
