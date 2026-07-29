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

/** Returns all available languages. */
export function getAvailableLanguages(): LanguageCode[] {
  return Object.keys(translations) as LanguageCode[];
}

export type { Translation };
