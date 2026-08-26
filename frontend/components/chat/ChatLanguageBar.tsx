'use client';
import { useState } from 'react';
import { Globe, X } from 'lucide-react';

const LANG_OPTIONS = [
  { code: 'en', flag: '🇬🇧', label: 'English' },
  { code: 'fi', flag: '🇫🇮', label: 'Finnish' },
  { code: 'sv', flag: '🇸🇪', label: 'Swedish' },
  { code: 'es', flag: '🇪🇸', label: 'Spanish' },
  { code: 'fr', flag: '🇫🇷', label: 'French' },
  { code: 'no', flag: '🇳🇴', label: 'Norwegian' },
];

interface Props {
  courseLang: string;
  explanationLang: string | null;
  onExplainLangChange: (lang: string | null) => void;
}

export function ChatLanguageBar({ courseLang, explanationLang, onExplainLangChange }: Props) {
  const [pickerOpen, setPickerOpen] = useState(false);

  const courseOpt  = LANG_OPTIONS.find(l => l.code === courseLang);
  const explainOpt = LANG_OPTIONS.find(l => l.code === explanationLang);

  function handleDismiss() {
    onExplainLangChange(null);
    setPickerOpen(false);
  }

  return (
    <div className="shrink-0 border-b border-[var(--bd)] bg-[var(--bg)] px-4 py-1.5 flex items-center justify-end min-h-[34px]">
      {explanationLang ? (
        /* Active: course → explain pill */
        <div className="flex items-center gap-1.5 text-[11px]">
          <span className="text-[var(--tx7)]">Explaining in</span>
          <span className="text-blue-400 font-medium">
            {courseOpt?.flag} {courseOpt?.label}
          </span>
          <span className="text-[var(--tx8)]">→</span>
          <span className="text-blue-400 font-medium">
            {explainOpt?.flag} {explainOpt?.label}
          </span>
          <button
            onClick={handleDismiss}
            title="Disable bilingual mode"
            className="ml-1 text-blue-400/50 hover:text-blue-300 transition-colors"
          >
            <X size={12} />
          </button>
        </div>
      ) : pickerOpen ? (
        /* Picker open */
        <div className="flex items-center gap-1.5 flex-wrap justify-end">
          <span className="text-[var(--tx7)] text-[10px]">Explain in:</span>
          {LANG_OPTIONS.filter(l => l.code !== courseLang).map(l => (
            <button
              key={l.code}
              onClick={() => { onExplainLangChange(l.code); setPickerOpen(false); }}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]
                         bg-[var(--surface)] border border-[var(--bd)]
                         hover:border-blue-400/50 hover:text-blue-400
                         text-[var(--tx4)] transition-colors"
            >
              {l.flag} {l.label}
            </button>
          ))}
          <button
            onClick={() => setPickerOpen(false)}
            className="text-[var(--tx7)] hover:text-[var(--tx3)] transition-colors"
          >
            <X size={11} />
          </button>
        </div>
      ) : (
        /* Inactive: ghost button */
        <button
          onClick={() => setPickerOpen(true)}
          className="flex items-center gap-1 text-[10px] text-[var(--tx9)] hover:text-[var(--tx5)] transition-colors group"
          title="Enable bilingual mode"
        >
          <Globe size={11} className="group-hover:text-blue-400/70 transition-colors" />
          <span>
            {courseOpt?.flag ?? '🌐'} {courseOpt?.label}
          </span>
          <span className="text-[var(--tx9)] opacity-0 group-hover:opacity-100 transition-opacity ml-0.5">
            · bilingual mode
          </span>
        </button>
      )}
    </div>
  );
}
