'use client';
import { useEffect } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { useLanguageStore } from '@/store/languageStore';
import { updateLanguage as apiUpdateLanguage } from '@/lib/api';
import type { LanguageCode } from '@/translations';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useLanguage() {
  const { user, token, setUser, institutionLanguage, setInstitutionLanguage } = useSessionStore();
  const { language, setLanguage: setStore } = useLanguageStore();

  // On login: fetch institution language first; if set it overrides user.language
  useEffect(() => {
    if (!user?.id || !token) {
      setInstitutionLanguage(null);
      return;
    }
    fetch(`${API_BASE}/api/institutions/my-lang`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : { language: null })
      .then(({ language: instLang }) => {
        setInstitutionLanguage(instLang ?? null);
        const resolved = instLang ?? user.language ?? 'en';
        if (resolved !== language) setStore(resolved as LanguageCode);
      })
      .catch(() => {
        // Fall back to user.language
        const dbLang = user.language;
        if (dbLang && dbLang !== language) setStore(dbLang as LanguageCode);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  function setLanguage(lang: LanguageCode) {
    if (institutionLanguage) return; // locked by institution
    setStore(lang);
    if (user && token) {
      apiUpdateLanguage(user.id, lang, token).catch(() => {});
      setUser({ ...user, language: lang }, token);
    }
  }

  return { language, setLanguage, institutionLanguage };
}
