'use client';
import { useEffect } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { useLanguageStore } from '@/store/languageStore';
import { updateLanguage as apiUpdateLanguage } from '@/lib/api';
import { getAvailableLanguages } from '@/translations';
import type { LanguageCode } from '@/translations';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useLanguage() {
  const { user, token, setUser, institutionLanguages, setInstitutionLanguages } = useSessionStore();
  const { language, setLanguage: setStore } = useLanguageStore();

  // On login: fetch institution languages; restrict or lock accordingly
  useEffect(() => {
    if (!user?.id || !token) {
      setInstitutionLanguages(null);
      return;
    }
    fetch(`${API_BASE}/api/institutions/my-lang`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : { languages: null })
      .then(({ languages: instLangs }: { languages: string[] | null }) => {
        setInstitutionLanguages(instLangs && instLangs.length > 0 ? instLangs : null);
        if (instLangs && instLangs.length > 0) {
          // If current language not in allowed set, snap to first allowed
          if (!instLangs.includes(language)) {
            setStore(instLangs[0] as LanguageCode);
          }
        } else {
          // No restriction — apply saved user.language if set
          const dbLang = user.language;
          if (dbLang && dbLang !== language) setStore(dbLang as LanguageCode);
        }
      })
      .catch(() => {
        const dbLang = user.language;
        if (dbLang && dbLang !== language) setStore(dbLang as LanguageCode);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  /** Languages the user may choose from (null means unrestricted). */
  const availableLanguages = (institutionLanguages ?? getAvailableLanguages()) as LanguageCode[];

  function setLanguage(lang: LanguageCode) {
    if (institutionLanguages && !institutionLanguages.includes(lang)) return;
    setStore(lang);
    if (user && token) {
      apiUpdateLanguage(user.id, lang, token).catch(() => {});
      setUser({ ...user, language: lang }, token);
    }
  }

  return { language, setLanguage, availableLanguages, institutionLanguages };
}
