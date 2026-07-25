'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, Loader2, Users } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Cell {
  visited: boolean;
  quiz_score: number | null;
  last_seen_at: string | null;
  flashcard_pct: number | null;
  flashcard_mastered: number;
  flashcard_total: number;
  quiz_attempts: number[];
  video_blocks_total: number;
  video_blocks_watched: number;
}
interface Concept     { id: string; title: string; unit_title: string; }
interface StudentRow  {
  id: string; name: string; email: string;
  visited_count: number; avg_quiz_score: number | null;
  last_seen_at: string | null;
  cells: Record<string, Cell>;
}
interface ProgressData {
  course_id: string; course_name: string;
  concepts: Concept[]; students: StudentRow[];
}

// Mastery level derived from visited + quiz_score
type Mastery = 'none' | 'visited' | 'struggling' | 'practiced' | 'mastered';

function getMastery(cell?: Cell): Mastery {
  if (!cell?.visited) return 'none';
  if (cell.quiz_score === null) return 'visited';
  if (cell.quiz_score >= 70) return 'mastered';
  if (cell.quiz_score >= 40) return 'practiced';
  return 'struggling';
}

const MASTERY_DOT: Record<Mastery, string> = {
  none:       'w-2.5 h-2.5 rounded-full bg-[var(--ov3)]',
  visited:    'w-2.5 h-2.5 rounded-full bg-blue-400',
  struggling: 'w-2.5 h-2.5 rounded-full bg-red-400',
  practiced:  'w-2.5 h-2.5 rounded-full bg-amber-400',
  mastered:   'w-2.5 h-2.5 rounded-full bg-green-400',
};

const MASTERY_BG: Record<Mastery, string> = {
  none:       '',
  visited:    'bg-blue-500/5',
  struggling: 'bg-red-500/8',
  practiced:  'bg-amber-500/8',
  mastered:   'bg-green-500/8',
};

function relativeTime(iso: string | null, tt: { relToday: string; relDaysAgo: string; relWeeksAgo: string; relMonthsAgo: string }): string {
  if (!iso) return '—';
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days === 0) return tt.relToday;
  if (days < 7)  return tt.relDaysAgo.replace('{n}', String(days));
  if (days < 30) return tt.relWeeksAgo.replace('{n}', String(Math.floor(days / 7)));
  return tt.relMonthsAgo.replace('{n}', String(Math.floor(days / 30)));
}

function lastSeenColor(iso: string | null): string {
  if (!iso) return 'text-[var(--tx8)]';
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days > 7)  return 'text-red-400';
  if (days > 3)  return 'text-amber-400';
  return 'text-[var(--tx6)]';
}

export default function CourseProgressPage() {
  const router   = useRouter();
  const params   = useParams();
  const courseId = params.id as string;
  const { user, token } = useSessionStore();
  const { t } = useTranslation();

  const [data,    setData]    = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user, courseId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/progress`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { router.replace(`/teacher/courses/${courseId}`); return; }
      setData(await res.json());
    } finally { setLoading(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!data) return null;

  // Class averages per concept (for the bottom row)
  const conceptAvgScores: Record<string, number | null> = {};
  for (const c of data.concepts) {
    const scores = data.students
      .map(s => s.cells[c.id]?.quiz_score)
      .filter((v): v is number => v !== null && v !== undefined);
    conceptAvgScores[c.id] = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  }

  return (
    <div className="p-6 max-w-full mx-auto pb-16">

      <button onClick={() => router.push(`/teacher/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> {t.teacher.backToCourse}
      </button>

      <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{data.course_name}</h1>
      <p className="text-[var(--tx7)] text-sm mb-4 flex items-center gap-1.5">
        <Users size={13} /> {data.students.length} student{data.students.length === 1 ? '' : 's'} · {data.concepts.length} concepts
      </p>

      {/* Mastery legend */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 mb-5 text-xs text-[var(--tx6)]">
        {(['none','visited','struggling','practiced','mastered'] as Mastery[]).map(m => (
          <span key={m} className="flex items-center gap-1.5">
            <span className={MASTERY_DOT[m]} />
            {m === 'none'       ? t.teacher.masteryNone
            : m === 'visited'   ? t.teacher.masteryVisited
            : m === 'struggling'? t.teacher.masteryStruggling
            : m === 'practiced' ? t.teacher.masteryPracticed
            :                     t.teacher.masteryMastered}
          </span>
        ))}
      </div>

      {data.students.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">{t.teacher.noStudentsEnrolled}</p>
        </div>
      ) : data.concepts.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">{t.teacher.noConceptsProgress}</p>
        </div>
      ) : (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-[var(--bd)]">
                <th className="text-left p-3 text-[var(--tx7)] font-medium sticky left-0 bg-[var(--surface)] min-w-[180px]">
                  {t.teacher.colStudent}
                </th>
                <th className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap">{t.teacher.colVisited}</th>
                <th className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap">{t.teacher.colAvgQuiz}</th>
                <th className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap">{t.teacher.colLastActive}</th>
                {data.concepts.map(c => (
                  <th key={c.id} className="text-center p-2 text-[var(--tx7)] font-medium min-w-[90px] max-w-[110px]" title={c.title}>
                    <div className="truncate text-xs">{c.title}</div>
                    <div className="text-[var(--tx8)] text-[10px] font-normal truncate">{c.unit_title}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.students.map(s => (
                <tr key={s.id} className="border-b border-[var(--bd)] last:border-0 hover:bg-[var(--ov1)]">
                  {/* Student name — clickable */}
                  <td className="p-3 sticky left-0 bg-[var(--surface)]">
                    <button onClick={() => router.push(`/teacher/students/${s.id}`)}
                      className="text-left hover:text-purple-400 transition-colors">
                      <p className="text-[var(--tx1)] font-medium">{s.name}</p>
                      <p className="text-[var(--tx8)] text-xs">{s.email}</p>
                    </button>
                  </td>
                  <td className="text-center p-3 text-[var(--tx2)] whitespace-nowrap text-xs">
                    {s.visited_count}/{data.concepts.length}
                  </td>
                  <td className="text-center p-3 whitespace-nowrap">
                    {s.avg_quiz_score !== null ? (
                      <span className={`text-xs font-medium ${
                        s.avg_quiz_score >= 70 ? 'text-green-400' : s.avg_quiz_score >= 40 ? 'text-amber-400' : 'text-red-400'
                      }`}>{Math.round(s.avg_quiz_score)}%</span>
                    ) : <span className="text-[var(--tx8)] text-xs">—</span>}
                  </td>
                  {/* Last active */}
                  <td className={`text-center p-3 text-xs whitespace-nowrap ${lastSeenColor(s.last_seen_at)}`}>
                    {relativeTime(s.last_seen_at, t.teacher)}
                  </td>
                  {/* Per-concept mastery cells */}
                  {data.concepts.map(c => {
                    const cell     = s.cells[c.id];
                    const m        = getMastery(cell);
                    const attempts = cell?.quiz_attempts ?? [];
                    const tipParts: string[] = [];
                    if (attempts.length > 1) tipParts.push(`Quiz: ${attempts.join(' → ')}%`);
                    else if (attempts.length === 1) tipParts.push(`Quiz: ${attempts[0]}%`);
                    if (cell?.video_blocks_total > 0) tipParts.push(`Videos: ${cell.video_blocks_watched}/${cell.video_blocks_total} watched (≥75%)`);
                    return (
                      <td key={c.id} className={`text-center p-2 ${MASTERY_BG[m]}`} title={tipParts.join(' · ') || undefined}>
                        <div className="flex flex-col items-center gap-0.5">
                          <span className={MASTERY_DOT[m]} />
                          {attempts.length > 0 && (
                            <span className="text-[10px] text-[var(--tx7)]">
                              {attempts[attempts.length - 1]}%
                              {attempts.length > 1 && (
                                <span className={attempts[attempts.length-1] > attempts[0] ? 'text-green-400' : attempts[attempts.length-1] < attempts[0] ? 'text-red-400' : ''}>
                                  {attempts[attempts.length-1] > attempts[0] ? ' ↑' : attempts[attempts.length-1] < attempts[0] ? ' ↓' : ''}
                                </span>
                              )}
                            </span>
                          )}
                          {cell?.video_blocks_total > 0 && (
                            <span className={`text-[9px] shrink-0 ${
                              cell.video_blocks_watched === cell.video_blocks_total ? 'text-green-400'
                              : cell.video_blocks_watched > 0 ? 'text-amber-400'
                              : 'text-[var(--tx8)]'
                            }`}>▶ {cell.video_blocks_watched}/{cell.video_blocks_total}</span>
                          )}
                          {cell?.flashcard_total > 0 && (
                            <span className="text-[9px] text-[var(--tx8)]">
                              {cell.flashcard_mastered}/{cell.flashcard_total} cards
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}

              {/* Class average row */}
              <tr className="border-t-2 border-[var(--bd)] bg-[var(--ov1)]">
                <td className="p-3 sticky left-0 bg-[var(--ov1)]">
                  <p className="text-[var(--tx6)] text-xs font-semibold uppercase tracking-wide">{t.teacher.classAvgRow}</p>
                </td>
                <td colSpan={3} />
                {data.concepts.map(c => {
                  const avg = conceptAvgScores[c.id];
                  return (
                    <td key={c.id} className="text-center p-2">
                      {avg !== null ? (
                        <span className={`text-xs font-medium ${
                          avg >= 70 ? 'text-green-400' : avg >= 40 ? 'text-amber-400' : 'text-red-400'
                        }`}>{Math.round(avg)}%</span>
                      ) : <span className="text-[var(--tx8)] text-[10px]">—</span>}
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
