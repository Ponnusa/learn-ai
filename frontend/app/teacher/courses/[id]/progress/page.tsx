'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Loader2, Users, ExternalLink,
  Layers, Video, BarChart2, ChevronDown, ChevronUp, HelpCircle,
} from 'lucide-react';
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

interface QuizAnalyticsQuestion {
  qi: number; question: string;
  correct_pct: number; attempt_count: number;
  most_wrong_option: string | null;
}
interface QuizAnalyticsData {
  concept_id: string; total_attempts: number;
  questions: QuizAnalyticsQuestion[];
}

type Mastery = 'none' | 'visited' | 'struggling' | 'practiced' | 'mastered';
type ViewMode = 'students' | 'concepts';
type SortBy   = 'title' | 'quiz' | 'mastered' | 'struggling';

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

function ScoreBar({ pct, className = '' }: { pct: number; className?: string }) {
  const color = pct >= 70 ? 'bg-green-400' : pct >= 40 ? 'bg-amber-400' : 'bg-red-400';
  return (
    <div className={`h-1 bg-[var(--ov3)] rounded-full overflow-hidden ${className}`}>
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function CourseProgressPage() {
  const router   = useRouter();
  const params   = useParams();
  const courseId = params.id as string;
  const { user, token } = useSessionStore();
  const { t } = useTranslation();

  const [data,    setData]    = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);

  // View toggle & concept-level class analytics
  const [viewMode,         setViewMode]         = useState<ViewMode>('students');
  const [sortBy,           setSortBy]           = useState<SortBy>('struggling');
  const [expandedConcept,  setExpandedConcept]  = useState<string | null>(null);
  const [conceptAnalytics, setConceptAnalytics] = useState<Record<string, QuizAnalyticsData | null | 'loading'>>({});

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

  async function toggleConceptAnalytics(conceptId: string) {
    if (expandedConcept === conceptId) { setExpandedConcept(null); return; }
    setExpandedConcept(conceptId);
    if (conceptId in conceptAnalytics) return;
    setConceptAnalytics(prev => ({ ...prev, [conceptId]: 'loading' }));
    try {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/quiz-analytics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = res.ok ? await res.json() : null;
      setConceptAnalytics(prev => ({ ...prev, [conceptId]: d }));
    } catch {
      setConceptAnalytics(prev => ({ ...prev, [conceptId]: null }));
    }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!data) return null;

  // ── Shared computed values ───────────────────────────────────────────────

  const conceptAvgScores: Record<string, number | null> = {};
  for (const c of data.concepts) {
    const scores = data.students
      .map(s => s.cells[c.id]?.quiz_score)
      .filter((v): v is number => v !== null && v !== undefined);
    conceptAvgScores[c.id] = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  }

  type UnitGroup = { title: string; concepts: Concept[] };
  const unitGroups: UnitGroup[] = [];
  for (const c of data.concepts) {
    const last = unitGroups[unitGroups.length - 1];
    if (last && last.title === c.unit_title) last.concepts.push(c);
    else unitGroups.push({ title: c.unit_title, concepts: [c] });
  }

  const unitAvgScores: Record<string, number | null> = {};
  for (const ug of unitGroups) {
    const scores = ug.concepts
      .flatMap(c => data.students.map(s => s.cells[c.id]?.quiz_score))
      .filter((v): v is number => v !== null && v !== undefined);
    unitAvgScores[ug.title] = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  }

  // ── Per-concept aggregate stats (for concept view) ───────────────────────

  const conceptStats = data.concepts.map(c => {
    const cells       = data.students.map(s => s.cells[c.id]).filter(Boolean) as Cell[];
    const visited     = cells.filter(cell => cell.visited);
    const withQuiz    = cells.filter(cell => cell.quiz_score !== null);
    const avgQuiz     = withQuiz.length > 0
      ? withQuiz.reduce((sum, cell) => sum + (cell.quiz_score ?? 0), 0) / withQuiz.length
      : null;
    const mastered    = cells.filter(cell => cell.visited && (cell.quiz_score ?? -1) >= 70).length;
    const struggling  = cells.filter(cell => cell.visited && cell.quiz_score !== null && cell.quiz_score < 40).length;
    const fcStudents  = cells.filter(cell => cell.flashcard_total > 0);
    const avgFc       = fcStudents.length > 0
      ? fcStudents.reduce((sum, cell) => sum + (cell.flashcard_pct ?? 0), 0) / fcStudents.length
      : null;
    const vidStudents = cells.filter(cell => cell.video_blocks_total > 0);
    const vidDone     = vidStudents.filter(cell => cell.video_blocks_watched === cell.video_blocks_total).length;
    return {
      concept: c,
      visitedCount:    visited.length,
      totalStudents:   data.students.length,
      avgQuizScore:    avgQuiz,
      masteredCount:   mastered,
      strugglingCount: struggling,
      avgFlashcardPct: avgFc,
      videoCompleted:  vidDone,
      videoStudents:   vidStudents.length,
    };
  });

  const sortedStats = [...conceptStats].sort((a, b) => {
    if (sortBy === 'quiz')       return (a.avgQuizScore ?? 101) - (b.avgQuizScore ?? 101);
    if (sortBy === 'mastered')   return b.masteredCount - a.masteredCount;
    if (sortBy === 'struggling') return b.strugglingCount - a.strugglingCount;
    return a.concept.title.localeCompare(b.concept.title);
  });

  // ── Render ───────────────────────────────────────────────────────────────

  const SortBtn = ({ id, label }: { id: SortBy; label: string }) => (
    <button
      onClick={() => setSortBy(id)}
      className={`text-[10px] px-2 py-0.5 rounded-full transition-colors ${
        sortBy === id
          ? 'bg-purple-600 text-white'
          : 'border border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="p-6 max-w-full mx-auto pb-16">

      <button onClick={() => router.push(`/teacher/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> {t.teacher.backToCourse}
      </button>

      {/* Header row */}
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{data.course_name}</h1>
          <p className="text-[var(--tx7)] text-sm flex items-center gap-1.5">
            <Users size={13} /> {data.students.length} student{data.students.length === 1 ? '' : 's'} · {data.concepts.length} concepts
          </p>
        </div>

        {/* View toggle */}
        {data.students.length > 0 && data.concepts.length > 0 && (
          <div className="flex items-center gap-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl p-1">
            <button
              onClick={() => setViewMode('students')}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                viewMode === 'students'
                  ? 'bg-[var(--surface)] text-[var(--tx1)] shadow-sm'
                  : 'text-[var(--tx6)] hover:text-[var(--tx2)]'
              }`}
            >
              <Users size={12} /> {t.teacher.progressViewStudents}
            </button>
            <button
              onClick={() => setViewMode('concepts')}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                viewMode === 'concepts'
                  ? 'bg-[var(--surface)] text-[var(--tx1)] shadow-sm'
                  : 'text-[var(--tx6)] hover:text-[var(--tx2)]'
              }`}
            >
              <BarChart2 size={12} /> {t.teacher.progressViewConcepts}
            </button>
          </div>
        )}
      </div>

      {/* Mastery legend — shown in student view */}
      {viewMode === 'students' && (
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
      )}

      {data.students.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">{t.teacher.noStudentsEnrolled}</p>
        </div>
      ) : data.concepts.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">{t.teacher.noConceptsProgress}</p>
        </div>

      ) : viewMode === 'concepts' ? (
        /* ══════════════════════════════════════════════════════════════════
           CONCEPT VIEW — one row per concept, sorted by difficulty signal
           ═════════════════════════════════════════════════════════════════ */
        <div className="space-y-3">
          {/* Sort controls */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[var(--tx7)] text-[11px]">{t.teacher.progressSortByLabel}</span>
            <SortBtn id="struggling" label={t.teacher.progressSortStruggling} />
            <SortBtn id="quiz"       label={t.teacher.progressSortLowestScore} />
            <SortBtn id="mastered"   label={t.teacher.progressSortMastered} />
            <SortBtn id="title"      label={t.teacher.progressSortTitle} />
          </div>

          {/* Concept cards */}
          <div className="space-y-2">
            {sortedStats.map(stat => {
              const c          = stat.concept;
              const isExpanded = expandedConcept === c.id;
              const analytics  = conceptAnalytics[c.id];
              const unitColor  = unitGroups.findIndex(ug => ug.title === c.unit_title) % 2 === 0
                ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                : 'bg-blue-500/10 text-blue-400 border-blue-500/20';

              return (
                <div key={c.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">
                  {/* ── Summary row ── */}
                  <div className="px-5 py-4">
                    <div className="flex items-center gap-3 flex-wrap">
                      {/* Title + unit + open link */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[var(--tx1)] font-medium text-sm">{c.title}</span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded-full border font-medium ${unitColor}`}>
                            {c.unit_title}
                          </span>
                          <button
                            onClick={() => router.push(`/teacher/courses/${courseId}/concepts/${c.id}`)}
                            className="flex items-center gap-0.5 text-[10px] text-[var(--tx7)] hover:text-purple-400 transition-colors ml-1"
                            title="Open concept page"
                          >
                            <ExternalLink size={10} />
                          </button>
                        </div>
                      </div>

                      {/* Stat chips */}
                      <div className="flex items-center gap-4 flex-wrap shrink-0">

                        {/* Students visited */}
                        <div className="text-center min-w-[56px]">
                          <p className="text-[10px] text-[var(--tx7)] mb-0.5">Visited</p>
                          <p className="text-sm font-semibold text-[var(--tx2)]">
                            {stat.visitedCount}<span className="text-[var(--tx8)] font-normal text-xs">/{stat.totalStudents}</span>
                          </p>
                          <ScoreBar pct={stat.totalStudents > 0 ? (stat.visitedCount / stat.totalStudents) * 100 : 0} className="mt-1 w-14" />
                        </div>

                        {/* Avg quiz */}
                        <div className="text-center min-w-[56px]">
                          <p className="text-[10px] text-[var(--tx7)] mb-0.5">Avg quiz</p>
                          {stat.avgQuizScore !== null ? (
                            <>
                              <p className={`text-sm font-semibold ${
                                stat.avgQuizScore >= 70 ? 'text-green-400' : stat.avgQuizScore >= 40 ? 'text-amber-400' : 'text-red-400'
                              }`}>{Math.round(stat.avgQuizScore)}%</p>
                              <ScoreBar pct={stat.avgQuizScore} className="mt-1 w-14" />
                            </>
                          ) : <p className="text-[var(--tx8)] text-xs mt-1">—</p>}
                        </div>

                        {/* Mastered */}
                        <div className="text-center min-w-[56px]">
                          <p className="text-[10px] text-[var(--tx7)] mb-0.5">Mastered</p>
                          <p className="text-sm font-semibold text-green-400">
                            {stat.masteredCount}<span className="text-[var(--tx8)] font-normal text-xs">/{stat.totalStudents}</span>
                          </p>
                          <div className="h-1 bg-[var(--ov3)] rounded-full overflow-hidden mt-1 w-14">
                            <div className="h-full rounded-full bg-green-400" style={{ width: `${stat.totalStudents > 0 ? (stat.masteredCount / stat.totalStudents) * 100 : 0}%` }} />
                          </div>
                        </div>

                        {/* Struggling */}
                        {stat.strugglingCount > 0 && (
                          <div className="text-center min-w-[56px]">
                            <p className="text-[10px] text-[var(--tx7)] mb-0.5">Struggling</p>
                            <p className="text-sm font-semibold text-red-400">
                              {stat.strugglingCount}<span className="text-[var(--tx8)] font-normal text-xs">/{stat.totalStudents}</span>
                            </p>
                            <div className="h-1 bg-[var(--ov3)] rounded-full overflow-hidden mt-1 w-14">
                              <div className="h-full rounded-full bg-red-400" style={{ width: `${stat.totalStudents > 0 ? (stat.strugglingCount / stat.totalStudents) * 100 : 0}%` }} />
                            </div>
                          </div>
                        )}

                        {/* Flashcards */}
                        {stat.avgFlashcardPct !== null && (
                          <div className="text-center min-w-[56px]">
                            <p className="text-[10px] text-[var(--tx7)] mb-0.5 flex items-center gap-0.5 justify-center">
                              <Layers size={8} /> Cards
                            </p>
                            <p className={`text-sm font-semibold ${
                              stat.avgFlashcardPct >= 70 ? 'text-green-400' : stat.avgFlashcardPct >= 40 ? 'text-amber-400' : 'text-[var(--tx6)]'
                            }`}>{Math.round(stat.avgFlashcardPct)}%</p>
                            <ScoreBar pct={stat.avgFlashcardPct} className="mt-1 w-14" />
                          </div>
                        )}

                        {/* Videos */}
                        {stat.videoStudents > 0 && (
                          <div className="text-center min-w-[56px]">
                            <p className="text-[10px] text-[var(--tx7)] mb-0.5 flex items-center gap-0.5 justify-center">
                              <Video size={8} /> Videos
                            </p>
                            <p className={`text-sm font-semibold ${
                              stat.videoCompleted === stat.videoStudents ? 'text-green-400' : stat.videoCompleted > 0 ? 'text-amber-400' : 'text-[var(--tx8)]'
                            }`}>
                              {stat.videoCompleted}<span className="text-[var(--tx8)] font-normal text-xs">/{stat.videoStudents}</span>
                            </p>
                            <div className="h-1 bg-[var(--ov3)] rounded-full overflow-hidden mt-1 w-14">
                              <div className={`h-full rounded-full ${stat.videoCompleted === stat.videoStudents ? 'bg-green-400' : 'bg-amber-400'}`}
                                style={{ width: `${stat.videoStudents > 0 ? (stat.videoCompleted / stat.videoStudents) * 100 : 0}%` }} />
                            </div>
                          </div>
                        )}

                        {/* Class quiz analytics toggle */}
                        {stat.avgQuizScore !== null && (
                          <button
                            onClick={() => toggleConceptAnalytics(c.id)}
                            className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded-lg border transition-colors shrink-0 ${
                              isExpanded
                                ? 'bg-purple-500/15 border-purple-500/40 text-purple-400'
                                : 'border-[var(--bd)] text-[var(--tx7)] hover:border-purple-500/40 hover:text-purple-400'
                            }`}
                            title="Class quiz analytics — which questions are hardest"
                          >
                            <HelpCircle size={10} />
                            {isExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* ── Class-wide quiz analytics panel ── */}
                  {isExpanded && (
                    <div className="border-t border-[var(--bd)] bg-[var(--ov1)] px-5 py-4">
                      <div className="flex items-center gap-2 mb-3">
                        <HelpCircle size={12} className="text-purple-400" />
                        <span className="text-xs font-medium text-[var(--tx2)]">Class quiz breakdown</span>
                        {analytics && analytics !== 'loading' && analytics !== null && (
                          <span className="text-[10px] text-[var(--tx7)]">
                            · {analytics.total_attempts} attempt{analytics.total_attempts !== 1 ? 's' : ''} across all students
                          </span>
                        )}
                      </div>

                      {analytics === 'loading' ? (
                        <div className="flex items-center justify-center py-5">
                          <Loader2 size={16} className="text-purple-400 animate-spin" />
                        </div>
                      ) : !analytics || analytics.total_attempts === 0 || analytics.questions.length === 0 ? (
                        <p className="text-[var(--tx7)] text-xs py-2">No attempt data yet for this concept</p>
                      ) : (
                        <div className="space-y-3 max-w-2xl">
                          {analytics.questions.map((q, qi) => (
                            <div key={q.qi}>
                              <div className="flex items-start gap-2 mb-1">
                                <span className="text-[10px] font-mono text-[var(--tx7)] shrink-0 mt-0.5">{qi + 1}.</span>
                                <p className="text-xs text-[var(--tx2)] flex-1">{q.question}</p>
                                <span className={`text-xs font-semibold shrink-0 ${
                                  q.correct_pct >= 70 ? 'text-green-400' : q.correct_pct >= 40 ? 'text-amber-400' : 'text-red-400'
                                }`}>{Math.round(q.correct_pct)}%</span>
                              </div>
                              <div className="ml-4">
                                <div className="h-1.5 bg-[var(--ov3)] rounded-full overflow-hidden mb-1">
                                  <div className={`h-full rounded-full ${
                                    q.correct_pct >= 70 ? 'bg-green-400' : q.correct_pct >= 40 ? 'bg-amber-400' : 'bg-red-400'
                                  }`} style={{ width: `${q.correct_pct}%` }} />
                                </div>
                                {q.most_wrong_option && (
                                  <p className="text-[10px] text-[var(--tx7)]">
                                    Most common wrong answer: <span className="text-red-400">{q.most_wrong_option}</span>
                                  </p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

      ) : (
        /* ══════════════════════════════════════════════════════════════════
           STUDENT VIEW — existing grid (students × concepts)
           ═════════════════════════════════════════════════════════════════ */
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              {/* Row 1 — unit spanning headers */}
              <tr className="border-b border-[var(--bd)/50]">
                <th rowSpan={2} className="text-left p-3 text-[var(--tx7)] font-medium sticky left-0 bg-[var(--surface)] min-w-[180px] border-b border-[var(--bd)]">
                  {t.teacher.colStudent}
                </th>
                <th rowSpan={2} className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap border-b border-[var(--bd)]">{t.teacher.colVisited}</th>
                <th rowSpan={2} className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap border-b border-[var(--bd)]">{t.teacher.colAvgQuiz}</th>
                <th rowSpan={2} className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap border-b border-[var(--bd)]">{t.teacher.colLastActive}</th>
                {unitGroups.map((ug, ui) => (
                  <th key={ug.title} colSpan={ug.concepts.length}
                    className={`text-center px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide border-b border-[var(--bd)] border-l border-l-[var(--bd)] ${
                      ui % 2 === 0 ? 'bg-purple-500/5 text-purple-400' : 'bg-blue-500/5 text-blue-400'
                    }`}>
                    <span className="truncate block max-w-[160px] mx-auto">{ug.title}</span>
                    {unitAvgScores[ug.title] !== null && (
                      <span className={`ml-1 text-[9px] font-normal opacity-80 ${
                        (unitAvgScores[ug.title] ?? 0) >= 70 ? 'text-green-400' :
                        (unitAvgScores[ug.title] ?? 0) >= 40 ? 'text-amber-400' : 'text-red-400'
                      }`}>
                        · {Math.round(unitAvgScores[ug.title] ?? 0)}% avg
                      </span>
                    )}
                  </th>
                ))}
              </tr>
              {/* Row 2 — individual concept columns */}
              <tr className="border-b border-[var(--bd)]">
                {data.concepts.map((c) => {
                  const isFirstInUnit = unitGroups.some(ug => ug.concepts[0]?.id === c.id);
                  return (
                    <th key={c.id} className={`text-center p-2 text-[var(--tx7)] font-medium min-w-[90px] max-w-[110px] ${isFirstInUnit ? 'border-l border-[var(--bd)]' : ''}`} title={c.title}>
                      <div className="truncate text-xs">{c.title}</div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {data.students.map(s => (
                <tr key={s.id} className="border-b border-[var(--bd)] last:border-0 hover:bg-[var(--ov1)]">
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
                  <td className={`text-center p-3 text-xs whitespace-nowrap ${lastSeenColor(s.last_seen_at)}`}>
                    {relativeTime(s.last_seen_at, t.teacher)}
                  </td>
                  {data.concepts.map((c) => {
                    const isFirstInUnit = unitGroups.some(ug => ug.concepts[0]?.id === c.id);
                    const cell     = s.cells[c.id];
                    const m        = getMastery(cell);
                    const attempts = cell?.quiz_attempts ?? [];
                    const tipParts: string[] = [];
                    if (attempts.length > 1) tipParts.push(`Quiz: ${attempts.join(' → ')}%`);
                    else if (attempts.length === 1) tipParts.push(`Quiz: ${attempts[0]}%`);
                    if (cell?.video_blocks_total > 0) tipParts.push(`Videos: ${cell.video_blocks_watched}/${cell.video_blocks_total} watched (≥75%)`);
                    return (
                      <td key={c.id} className={`text-center p-2 ${MASTERY_BG[m]} ${isFirstInUnit ? 'border-l border-[var(--bd)]' : ''}`} title={tipParts.join(' · ') || undefined}>
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
                  const isFirst = unitGroups.some(ug => ug.concepts[0]?.id === c.id);
                  return (
                    <td key={c.id} className={`text-center p-2 ${isFirst ? 'border-l border-[var(--bd)]' : ''}`}>
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
