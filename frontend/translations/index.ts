// Single import point for all translations.
// To add a language:
//   1. Create translations/xx.ts  (copy en.ts, translate values)
//   2. Import it here
//   3. Add to translations map + LANGUAGE_LABELS
//   4. Add to LanguageCode union type
// TypeScript will flag any missing keys.

import type { Translation } from './types';
import { en } from './en';
import { fi } from './fi';
import { sv } from './sv';
import { es } from './es';
import { fr } from './fr';
// import { de } from './de';
// import { et } from './et';
// import { no } from './no';

export type LanguageCode = 'en' | 'fi' | 'sv' | 'es' | 'fr';

export const translations: Record<LanguageCode, Translation> = {
  en,
  fi,
  sv,
  es,
  fr,
};

export const LANGUAGE_LABELS: Record<LanguageCode, string> = {
  en: '🇬🇧 English',
  fi: '🇫🇮 Suomi',
  sv: '🇸🇪 Svenska',
  es: '🇪🇸 Español',
  fr: '🇫🇷 Français',
};

export const LANGUAGE_NAMES: Record<LanguageCode, string> = {
  en: 'English',
  fi: 'Finnish',
  sv: 'Swedish',
  es: 'Spanish',
  fr: 'French',
};

export const DEFAULT_LANGUAGE: LanguageCode = 'en';

/** Country code → allowed LanguageCodes. DEFAULT catches everything else. */
export const COUNTRY_LANGUAGES: Record<string, LanguageCode[]> = {
  US: ['en', 'es', 'fr'],
  CA: ['en', 'fr'],
  MX: ['es', 'en'],
  FI: ['en', 'fi', 'sv'],
  SE: ['en', 'sv'],
  FR: ['fr', 'en'],
  ES: ['es', 'en'],
  IN: ['en'],
  DEFAULT: ['en', 'fi', 'sv', 'es', 'fr'],
};

/** Returns the languages available for the current user's detected country. */
export function getAvailableLanguages(): LanguageCode[] {
  if (typeof navigator === 'undefined') return COUNTRY_LANGUAGES['DEFAULT'];
  const parts = (navigator.language || '').split('-');
  const country = parts.length > 1 ? parts[parts.length - 1].toUpperCase() : 'DEFAULT';
  return COUNTRY_LANGUAGES[country] ?? COUNTRY_LANGUAGES['DEFAULT'];
}

export type { Translation };
