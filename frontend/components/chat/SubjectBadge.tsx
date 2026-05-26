'use client';

/*
 * Subject badge colours — using -600 shades for text so they are readable
 * on both dark surfaces (dark theme) and white surfaces (light theme).
 * Background uses low-opacity tints that look fine in both modes.
 */
const SUBJECT_COLORS: Record<string, string> = {
  Mathematics:            'bg-blue-500/10   text-blue-600   border-blue-500/20',
  Physics:                'bg-purple-500/10 text-purple-600 border-purple-500/20',
  Chemistry:              'bg-green-500/10  text-green-700  border-green-500/20',
  Biology:                'bg-emerald-500/10 text-emerald-700 border-emerald-500/20',
  'Computer Science':     'bg-slate-500/10  text-slate-600  border-slate-500/20',
  History:                'bg-amber-500/10  text-amber-700  border-amber-500/20',
  Geography:              'bg-cyan-500/10   text-cyan-700   border-cyan-500/20',
  Economics:              'bg-yellow-500/10 text-yellow-700 border-yellow-500/20',
  Literature:             'bg-rose-500/10   text-rose-600   border-rose-500/20',
  Philosophy:             'bg-violet-500/10 text-violet-600 border-violet-500/20',
  Psychology:             'bg-pink-500/10   text-pink-600   border-pink-500/20',
  Engineering:            'bg-orange-500/10 text-orange-600 border-orange-500/20',
  'Medicine & Health':    'bg-red-500/10    text-red-600    border-red-500/20',
  Business:               'bg-teal-500/10   text-teal-700   border-teal-500/20',
  Music:                  'bg-indigo-500/10 text-indigo-600 border-indigo-500/20',
  Law:                    'bg-stone-500/10  text-stone-600  border-stone-500/20',
  Other:                  'bg-[var(--ov2)]  text-[var(--tx5)] border-[var(--bd)]',
};

const SUBJECT_ICONS: Record<string, string> = {
  Mathematics: '📐', Physics: '⚛️', Chemistry: '🧪', Biology: '🧬',
  'Computer Science': '💻', History: '📜', Geography: '🌍', Economics: '📈',
  Literature: '📖', Philosophy: '🤔', Psychology: '🧠', Engineering: '⚙️',
  'Medicine & Health': '🏥', Business: '💼', Music: '🎵', Law: '⚖️',
  Other: '📚',
};

interface SubjectBadgeProps {
  subject: string;
  subtopic?: string;
}

export function SubjectBadge({ subject, subtopic }: SubjectBadgeProps) {
  if (!subject || subject === 'Other') return null;
  const color = SUBJECT_COLORS[subject] ?? SUBJECT_COLORS.Other;
  const icon  = SUBJECT_ICONS[subject]  ?? '📚';
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${color}`}>
      <span>{icon}</span>
      <span>{subtopic || subject}</span>
    </span>
  );
}
