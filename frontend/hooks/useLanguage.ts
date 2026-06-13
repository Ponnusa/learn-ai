'use client';
import { useEffect } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { useLanguageStore } from '@/store/languageStore';
import { updateLanguage as apiUpdateLanguage } from '@/lib/api';
import type { LanguageCode } from '@/translations';

export function useLanguage() {
  const { user, token, setUser } = useSessionStore();
  const { language, setLanguage: setStore } = useLanguageStore();

  // On login: apply DB language preference, overriding localStorage
  useEffect(() => {
    const dbLang = user?.language;
    if (dbLang && dbLang !== language) {
      setStore(dbLang);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, user?.language]);

  function setLanguage(lang: LanguageCode) {
    setStore(lang);
    if (user && token) {
      apiUpdateLanguage(user.id, lang, token).catch(() => {});
      setUser({ ...user, language: lang }, token);
    }
  }

  return { language, setLanguage };
}
