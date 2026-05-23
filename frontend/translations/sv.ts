// Swedish — stub. Import en as fallback and override keys as translated.
import type { Translation } from './types';
import { en } from './en';

export const sv: Translation = {
  ...en,
  appName: 'Learn-AI',
  tagline: 'Lär dig vad som helst, visuellt.',
  // TODO: translate all keys
};
