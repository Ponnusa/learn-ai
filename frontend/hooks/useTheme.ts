'use client';
import { useState, useEffect } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { updateTheme as apiUpdateTheme } from '@/lib/api';

export type Theme = 'dark' | 'light';

const KEY = 'learnai-theme';

export function useTheme() {
  const { user, token, setUser } = useSessionStore();
  const [theme, setThemeState]   = useState<Theme>('dark');

  // On mount and whenever the logged-in user changes (login / logout):
  // DB theme (user.theme) takes priority over localStorage.
  useEffect(() => {
    try {
      const dbTheme    = user?.theme;
      const localTheme = localStorage.getItem(KEY) as Theme | null;
      const resolved: Theme =
        dbTheme === 'light' || dbTheme === 'dark'   ? dbTheme   :
        localTheme === 'light' || localTheme === 'dark' ? localTheme : 'dark';

      setThemeState(resolved);
      localStorage.setItem(KEY, resolved);
      document.documentElement.setAttribute('data-theme', resolved);
    } catch {}
  }, [user?.id, user?.theme]);

  function setTheme(t: Theme) {
    setThemeState(t);
    try {
      localStorage.setItem(KEY, t);
      document.documentElement.setAttribute('data-theme', t);
    } catch {}

    // Persist to DB and update in-memory user object
    if (user && token) {
      apiUpdateTheme(user.id, t, token).catch(() => {});
      setUser({ ...user, theme: t }, token);
    }
  }

  return { theme, setTheme };
}
