'use client';
import { useState, useEffect } from 'react';

export type Theme = 'dark' | 'light';

const KEY = 'learnai-theme';

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>('dark');

  // Read saved preference after mount (avoids SSR mismatch)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY) as Theme | null;
      if (saved === 'light' || saved === 'dark') setThemeState(saved);
    } catch { /* localStorage unavailable */ }
  }, []);

  function setTheme(t: Theme) {
    setThemeState(t);
    try {
      localStorage.setItem(KEY, t);
      document.documentElement.setAttribute('data-theme', t);
    } catch { /* localStorage unavailable */ }
  }

  return { theme, setTheme };
}
