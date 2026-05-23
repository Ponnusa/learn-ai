'use client';

const SUBJECT_COLORS: Record<string, string> = {
  Mathematics:            'bg-blue-500/20 text-blue-300 border-blue-500/30',
  Physics:                'bg-purple-500/20 text-purple-300 border-purple-500/30',
  Chemistry:              'bg-green-500/20 text-green-300 border-green-500/30',
  Biology:                'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'Computer Science':     'bg-gray-500/20 text-gray-300 border-gray-500/30',
  History:                'bg-amber-500/20 text-amber-300 border-amber-500/30',
  Geography:              'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  Economics:              'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  Literature:             'bg-rose-500/20 text-rose-300 border-rose-500/30',
  Philosophy:             'bg-violet-500/20 text-violet-300 border-violet-500/30',
  Psychology:             'bg-pink-500/20 text-pink-300 border-pink-500/30',
  Engineering:            'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'Medicine & Health':    'bg-red-500/20 text-red-300 border-red-500/30',
  Business:               'bg-teal-500/20 text-teal-300 border-teal-500/30',
  Music:                  'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  Law:                    'bg-stone-500/20 text-stone-300 border-stone-500/30',
  Other:                  'bg-white/10 text-white/50 border-white/20',
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
