'use client';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { LanguageCode } from '@/translations';

interface LanguageState {
  language: LanguageCode;
  setLanguage: (lang: LanguageCode) => void;
}

export const useLanguageStore = create<LanguageState>()(
  persist(
    (set) => ({
      language: 'en',
      setLanguage: (language) => set({ language }),
    }),
    { name: 'learnai-language' }
  )
);
