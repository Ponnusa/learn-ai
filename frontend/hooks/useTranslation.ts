'use client';
import { useLanguageStore } from '@/store/languageStore';
import { translations, DEFAULT_LANGUAGE } from '@/translations';

export function useTranslation() {
  const { language } = useLanguageStore();
  const t = translations[language] ?? translations[DEFAULT_LANGUAGE];

  /** Replace {placeholder} tokens in a translation string.
   *  Usage: tF(t.quiz.score, { score: 3, total: 5 }) → "You scored 3 out of 5" */
  function tF(template: string, vars: Record<string, string | number>): string {
    return Object.entries(vars).reduce(
      (str, [k, v]) => str.replaceAll(`{${k}}`, String(v)),
      template
    );
  }

  return { t, tF, language };
}
