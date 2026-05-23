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
// import { de } from './de';
// import { fr } from './fr';
// import { es } from './es';
// import { et } from './et';
// import { no } from './no';

export type LanguageCode = 'en' | 'fi' | 'sv';
//  | 'de' | 'fr' | 'es' | 'et' | 'no'   ← uncomment as added

export const translations: Record<LanguageCode, Translation> = {
  en,
  fi,
  sv,
};

export const LANGUAGE_LABELS: Record<LanguageCode, string> = {
  en: '🇬🇧 English',
  fi: '🇫🇮 Suomi',
  sv: '🇸🇪 Svenska',
};

export const LANGUAGE_NAMES: Record<LanguageCode, string> = {
  en: 'English',
  fi: 'Finnish',
  sv: 'Swedish',
};

export const DEFAULT_LANGUAGE: LanguageCode = 'en';

export type { Translation };
