'use client';
import { useTranslation } from '@/hooks/useTranslation';

const VIDEO_SUPPORTED  = ['Mathematics', 'Physics', 'Chemistry'];
const COMING_SOON      = ['Computer Science', 'Biology', 'Engineering', 'Economics', 'Psychology', 'Medicine & Health', 'Music'];
// Others: hide button completely

type VideoSupport = 'supported' | 'coming_soon' | 'not_planned' | 'unknown';

function getSupport(subject: string | null): VideoSupport {
  if (!subject)                          return 'unknown';
  if (VIDEO_SUPPORTED.includes(subject)) return 'supported';
  if (COMING_SOON.includes(subject))     return 'coming_soon';
  return 'not_planned';
}

interface Props {
  subject: string | null;
  onClick?: () => void;
}

export function MakeVisualButton({ subject, onClick }: Props) {
  const { t } = useTranslation();
  const support = getSupport(subject);

  if (support === 'not_planned') return null;

  if (support === 'coming_soon') {
    return (
      <button
        disabled
        title={subject ? t.video.comingSoonForSubject.replace('{subject}', subject) : t.video.comingSoonForSubject}
        className="text-xs px-3 py-1.5 rounded-lg bg-white/5 text-white/30 cursor-not-allowed flex items-center gap-1.5"
      >
        🎬 {t.video.comingSoonForSubject.replace('{subject}', subject ?? '')}
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className="text-xs px-3 py-1.5 rounded-lg bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 hover:text-purple-200 transition-colors flex items-center gap-1.5 border border-purple-500/30"
    >
      {t.chat.makeItVisual}
    </button>
  );
}
