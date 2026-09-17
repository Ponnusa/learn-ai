'use client';
import { useCallback, useEffect, useState } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import {
  ArrowLeft, Loader2, Brain, MessageSquare, ChevronDown, ChevronUp,
  Sparkles, HelpCircle, Layers, Video, BookOpen, AlertTriangle,
  CheckCircle2, Circle, Clock, Zap, TrendingUp, TrendingDown, Minus, Footprints, Target, Star, RotateCcw, XCircle,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import { LevelPill } from '@/components/course/LadderReportModal';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Temporarily restricting Assign Extra Practice to quiz/flashcards while
// video/study-set generation for this flow gets more attention — greyed
// out rather than removed so re-enabling later is a one-line change.
const DISABLED_ASSIGN_KINDS = new Set(['video', 'studyset']);

interface LadderReportSummary {
  weak_dimension: string | null;
  weak_level: string | null;
  next_growth_step: string | null;
  suggested_next_topic: string | null;
  optional_extension: string | null;
}
interface ConceptProgress {
  id: string; title: string;
  visited: boolean; quiz_score: number | null;
  last_seen_at: string | null;
  flashcard_pct: number | null;
  flashcard_mastered: number; flashcard_total: number;
  ai_msg_count: number;
  quiz_attempts: number[];       // last 5 scores oldest→newest
  time_spent_seconds: number;
  video_blocks_total: number;
  video_blocks_watched: number;
  last_attempt_answers: QuizAnswer[] | null;
  guided_resolved_count: number;
  guided_avg_steps: number | null;
  ladder_report: LadderReportSummary | null;
  recommended_kind: string | null;
  recommend_reason: string | null;
}
interface CourseProgress  { id: string; name: string; concepts: ConceptProgress[]; }
interface StudentProgress { id: string; name: string; email: string; courses: CourseProgress[]; }

interface Profile {
  has_profile: boolean;
  skill_scores: Record<string, number>;
  known_misconceptions: string[];
  struggle_areas: string[];
  mastered_concepts: string[];
  grade: string | null; goal: string | null;
  avg_quiz_score: number | null; total_messages: number;
}

interface ConversationSummary {
  id: string; title: string; subject: string | null;
  message_count: number; last_message_at: string | null;
}
interface ChatMessage { role: string; content: string; created_at: string | null; }

interface QuizAnswer { qi: number; question: string; chosen: number; correct: number; ok: boolean; }
interface QuizAttempt { id: string; score: number; answers: QuizAnswer[] | null; taken_at: string | null; }

interface Assignment {
  id: string; concept_id: string | null; kind: string;
  title: string; status: string; created_at: string | null;
  score: number | null;
}
interface AssignmentQuizQuestion { question: string; options: string[]; correct_idx: number; explanation?: string; }
interface AssignmentFlashcard    { front: string; back: string; }
interface AssignmentDetail {
  id: string; kind: string; status: string;
  payload: AssignmentQuizQuestion[] | AssignmentFlashcard[] | null;
  score: number | null; answers: QuizAnswer[] | null;
}

interface RollupEntry {
  most_common: string | null; trend: 'up' | 'down' | 'flat' | 'insufficient'; session_count: number;
  most_common_confidence?: string | null; most_common_support_level?: string | null;
}
interface TrendPoint {
  date: string | null;
  academic_understanding: string | null;
  decision_making: string | null; justification: string | null;
  constraint_awareness: string | null; transfer: string | null;
}
interface CourseSummary {
  layer1: {
    total_concepts: number; visited_count: number; avg_quiz_score: number | null;
    mastered_count: number; guided_resolved_count: number; guided_avg_steps: number | null;
    last_active: string | null;
  };
  layer2: {
    academic_understanding: RollupEntry;
    thinking_radar: {
      decision_making: RollupEntry; justification: RollupEntry;
      constraint_awareness: RollupEntry; transfer: RollupEntry;
    };
    focus_recommendation: string | null;
    trend_series: TrendPoint[];
  };
  layer3: { narrative: string; updated_at: string | null; report_count: number } | null;
}

type Mastery = 'none' | 'visited' | 'struggling' | 'practiced' | 'mastered';

function getMastery(c: ConceptProgress): Mastery {
  if (!c.visited) return 'none';
  // A verified guided-discovery resolution (passed the transfer-check gate)
  // counts as mastery on its own — it's applying the idea to a genuinely
  // new case under an objective, non-self-graded check, at least as strong
  // a signal as a quiz score. Independent of quiz standing: a low quiz
  // score on a different day doesn't erase a real, verified demonstration.
  if (c.guided_resolved_count > 0) return 'mastered';
  if (c.quiz_score === null) return 'visited';
  if (c.quiz_score >= 70) return 'mastered';
  if (c.quiz_score >= 40) return 'practiced';
  return 'struggling';
}

function formatTime(seconds: number): string {
  if (seconds < 60)   return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

// Inline quiz score trend: "45 → 67 → 82%" with a coloured trend arrow
function QuizTrend({ attempts }: { attempts: number[] }) {
  if (attempts.length === 0) return null;
  if (attempts.length === 1) {
    const s = attempts[0];
    return (
      <span className={`text-xs font-medium ${s >= 70 ? 'text-green-400' : s >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
        {s}%
      </span>
    );
  }
  const first = attempts[0];
  const last  = attempts[attempts.length - 1];
  const up    = last > first;
  const same  = last === first;
  return (
    <span className="flex items-center gap-1 text-xs shrink-0">
      <span className="text-[var(--tx7)]">{attempts.join(' → ')}%</span>
      <span className={up ? 'text-green-400' : same ? 'text-[var(--tx7)]' : 'text-red-400'}>
        {up ? '↑' : same ? '→' : '↓'}
      </span>
    </span>
  );
}

function relativeTime(iso: string | null, tt: { relToday: string; relDaysAgo: string; relWeeksAgo: string; relMonthsAgo: string }): string {
  if (!iso) return '—';
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days === 0) return tt.relToday;
  if (days < 7)  return tt.relDaysAgo.replace('{n}', String(days));
  if (days < 30) return tt.relWeeksAgo.replace('{n}', String(Math.floor(days / 7)));
  return tt.relMonthsAgo.replace('{n}', String(Math.floor(days / 30)));
}

function isAtRisk(course: CourseProgress): boolean {
  const visited    = course.concepts.filter(c => c.visited);
  if (visited.length === 0) return false;
  const avg        = visited.reduce((s, c) => s + (c.quiz_score ?? 100), 0) / visited.length;
  const lastActive = course.concepts
    .map(c => c.last_seen_at ? new Date(c.last_seen_at).getTime() : 0)
    .reduce((a, b) => Math.max(a, b), 0);
  const daysSince  = lastActive ? (Date.now() - lastActive) / 86_400_000 : 999;
  return avg < 50 || daysSince > 7;
}

// Stacked mastery bar for a course
function MasteryBar({ concepts }: { concepts: ConceptProgress[] }) {
  const counts = { mastered: 0, practiced: 0, visited: 0, struggling: 0, none: 0 };
  for (const c of concepts) counts[getMastery(c)]++;
  const total = concepts.length;
  if (total === 0) return null;
  const pct = (n: number) => `${(n / total * 100).toFixed(1)}%`;
  return (
    <div className="space-y-1">
      <div className="flex h-2 rounded-full overflow-hidden gap-px">
        {counts.mastered   > 0 && <div className="bg-green-500"  style={{ width: pct(counts.mastered) }}   title={`Mastered: ${counts.mastered}`} />}
        {counts.practiced  > 0 && <div className="bg-amber-500"  style={{ width: pct(counts.practiced) }}  title={`Practiced: ${counts.practiced}`} />}
        {counts.visited    > 0 && <div className="bg-blue-400"   style={{ width: pct(counts.visited) }}    title={`Visited: ${counts.visited}`} />}
        {counts.struggling > 0 && <div className="bg-red-500"    style={{ width: pct(counts.struggling) }} title={`Struggling: ${counts.struggling}`} />}
        {counts.none       > 0 && <div className="bg-[var(--ov3)]" style={{ width: pct(counts.none) }}     title={`Not started: ${counts.none}`} />}
      </div>
      <div className="flex gap-3 text-[10px] text-[var(--tx7)] flex-wrap">
        {counts.mastered   > 0 && <span className="text-green-400">{counts.mastered} mastered</span>}
        {counts.practiced  > 0 && <span className="text-amber-400">{counts.practiced} practiced</span>}
        {counts.visited    > 0 && <span className="text-blue-400">{counts.visited} visited</span>}
        {counts.struggling > 0 && <span className="text-red-400">{counts.struggling} struggling</span>}
        {counts.none       > 0 && <span>{counts.none} not started</span>}
      </div>
    </div>
  );
}

const DIMENSION_LABELS: [keyof CourseSummary['layer2']['thinking_radar'], string][] = [
  ['decision_making', 'Decision-Making'],
  ['justification', 'Justification'],
  ['constraint_awareness', 'Constraint Awareness'],
  ['transfer', 'Transfer'],
];

function TrendIcon({ trend }: { trend: RollupEntry['trend'] }) {
  if (trend === 'up')   return <TrendingUp size={11} className="text-green-400" />;
  if (trend === 'down') return <TrendingDown size={11} className="text-red-400" />;
  if (trend === 'flat') return <Minus size={11} className="text-[var(--tx7)]" />;
  return null; // 'insufficient' — not enough sessions to call a trend yet
}

const TREND_LEVEL_RANK: Record<string, number> = {
  'Limited Evidence': 0, 'Beginner': 1, 'Developing': 2, 'Proficient': 3, 'Advanced': 4,
};
const TREND_SERIES: { key: keyof TrendPoint; label: string; color: string; dot: string; width: number }[] = [
  // `dot` is spelled out explicitly (not derived from `color` via string
  // replace) because Tailwind's build-time scanner only picks up class
  // names that appear literally in source — a computed 'bg-' + shade
  // string is invisible to it and silently produces no CSS at all, which
  // is exactly why the constraint-awareness legend swatch had no color.
  { key: 'academic_understanding', label: 'Overall',              color: 'text-purple-400', dot: 'bg-purple-400', width: 2.5 },
  { key: 'decision_making',        label: 'Decision-Making',      color: 'text-blue-400',   dot: 'bg-blue-400',   width: 1.5 },
  { key: 'justification',          label: 'Justification',        color: 'text-amber-400',  dot: 'bg-amber-400',  width: 1.5 },
  { key: 'constraint_awareness',   label: 'Constraint Awareness', color: 'text-pink-400',   dot: 'bg-pink-400',   width: 1.5 },
  { key: 'transfer',               label: 'Transfer',             color: 'text-cyan-400',   dot: 'bg-cyan-400',   width: 1.5 },
];

/** Level-over-time line chart across a student's dated ladder session
 *  reports for one course — the rollup above only gives a net up/down/flat
 *  direction; this shows the actual trajectory a teacher can read at a
 *  glance. Hand-rolled SVG rather than a charting library: five short
 *  categorical (0-4 rank) series, well within what plain polylines handle
 *  cleanly. Needs at least two sessions to be a "trend" at all. */
function TrendChart({ series }: { series: TrendPoint[] }) {
  if (series.length < 2) return null;
  const rankOf = (level: string | null) => TREND_LEVEL_RANK[level ?? ''] ?? 0;
  const x = (i: number) => 20 + (i * 270) / (series.length - 1);
  const y = (rank: number) => 90 - rank * 20;

  return (
    <div className="border border-[var(--bd)] rounded-xl p-3.5 bg-[var(--surface)]">
      <p className="text-[10px] text-[var(--tx7)] uppercase tracking-wide mb-2">Level over time ({series.length} sessions)</p>
      <svg viewBox="0 0 300 100" className="w-full h-auto" preserveAspectRatio="none">
        {[0, 1, 2, 3, 4].map(rank => (
          <line key={rank} x1={18} x2={292} y1={y(rank)} y2={y(rank)} className="stroke-[var(--bd)]" strokeWidth={0.5} />
        ))}
        {['Ltd', 'Beg', 'Dev', 'Prof', 'Adv'].map((label, rank) => (
          <text key={label} x={0} y={y(rank) + 3} className="fill-[var(--tx8)]" fontSize={7}>{label}</text>
        ))}
        {TREND_SERIES.map(s => {
          const points = series.map((p, i) => `${x(i)},${y(rankOf(p[s.key]))}`).join(' ');
          return (
            <g key={s.key} className={s.color}>
              <polyline points={points} fill="none" stroke="currentColor" strokeWidth={s.width}
                strokeLinejoin="round" strokeLinecap="round" opacity={0.9} />
              {series.map((p, i) => (
                <circle key={i} cx={x(i)} cy={y(rankOf(p[s.key]))} r={s.width} fill="currentColor">
                  <title>{`${s.label}: ${p[s.key] ?? 'Limited Evidence'}${p.date ? ` (${p.date})` : ''}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      <div className="flex justify-between text-[9px] text-[var(--tx8)] mt-0.5 px-[18px]">
        <span>{series[0].date}</span>
        <span>{series[series.length - 1].date}</span>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
        {TREND_SERIES.map(s => (
          <span key={s.key} className="flex items-center gap-1 text-[10px] text-[var(--tx7)]">
            <span className={`w-2 h-2 rounded-full ${s.dot}`} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/** "Complete result" panel — three layers: quantitative roll-up (free),
 *  deterministic Thinking Radar rollup across all resolved ladder session
 *  reports (also free — the reports are already structured JSON), and a
 *  cached AI narrative synthesizing the trajectory across those reports. */
function CourseSummaryPanel({ summary, onRegenerate, regenerating }: { summary: CourseSummary; onRegenerate?: () => void; regenerating?: boolean }) {
  const { layer1, layer2, layer3 } = summary;
  return (
    <div className="space-y-4">
      {/* Layer 1 — quantitative roll-up */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        {[
          ['Visited', `${layer1.visited_count}/${layer1.total_concepts}`, undefined],
          ['Avg quiz', layer1.avg_quiz_score !== null ? `${Math.round(layer1.avg_quiz_score)}%` : '—', 'Average score across formal quiz attempts only — a low score here does not lower Mastered below, see that stat\'s own note.'],
          ['Mastered', `${layer1.mastered_count}/${layer1.total_concepts}`, 'A concept counts as mastered if the student either scored 70%+ on its quiz OR resolved at least one verified guided-discovery session for it — whichever happens first. Independent of the Avg quiz number above.'],
          ['Guided', String(layer1.guided_resolved_count), 'Guided-discovery chains resolved and verified by an independent check, not just self-reported by the AI tutor.'],
          ['Avg steps', layer1.guided_avg_steps !== null ? layer1.guided_avg_steps.toFixed(1) : '—', 'Average number of guiding questions per resolved chain — higher can mean more scaffolding was needed, not necessarily a problem.'],
          ['Last active', layer1.last_active ? new Date(layer1.last_active).toLocaleDateString() : '—', undefined],
        ].map(([label, value, tooltip]) => (
          <div key={label} className="text-center" title={tooltip}>
            <p className="text-[9px] text-[var(--tx7)] uppercase tracking-wide mb-0.5">{label}</p>
            <p className="text-sm font-semibold text-[var(--tx1)]">{value}</p>
          </div>
        ))}
      </div>

      {/* Layer 2 — Thinking Radar rollup across resolved sessions */}
      {layer2.academic_understanding.session_count > 0 ? (
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] text-[var(--tx7)] uppercase tracking-wide flex items-center gap-1">
              <Footprints size={10} /> Thinking Radar rollup ({layer2.academic_understanding.session_count} session{layer2.academic_understanding.session_count === 1 ? '' : 's'})
            </p>
            {layer2.focus_recommendation && (
              <span className="text-[10px] text-amber-400 flex items-center gap-1">
                <Target size={10} /> Focus: {layer2.focus_recommendation}
              </span>
            )}
          </div>
          <div className="grid sm:grid-cols-2 gap-2">
            <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--surface)] border border-[var(--bd)]">
              <span className="text-xs text-[var(--tx2)]">Academic Understanding</span>
              <span className="flex items-center gap-1.5">
                <TrendIcon trend={layer2.academic_understanding.trend} />
                {layer2.academic_understanding.most_common && <LevelPill level={layer2.academic_understanding.most_common} />}
              </span>
            </div>
            {DIMENSION_LABELS.map(([key, label]) => {
              const entry = layer2.thinking_radar[key];
              return (
                <div key={key} className="px-3 py-2 rounded-lg bg-[var(--surface)] border border-[var(--bd)]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[var(--tx2)]">{label}</span>
                    <span className="flex items-center gap-1.5">
                      <TrendIcon trend={entry.trend} />
                      {entry.most_common && <LevelPill level={entry.most_common} />}
                    </span>
                  </div>
                  {(entry.most_common_support_level || entry.most_common_confidence) && (
                    <p className="text-[9px] text-[var(--tx8)] mt-1">
                      {entry.most_common_support_level && <>Usually {entry.most_common_support_level.toLowerCase()}</>}
                      {entry.most_common_support_level && entry.most_common_confidence && ' · '}
                      {entry.most_common_confidence && <>{entry.most_common_confidence} confidence</>}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <p className="text-[var(--tx7)] text-xs">No guided-discovery sessions resolved yet in this course — the Thinking Radar rollup and narrative fill in once one resolves.</p>
      )}

      {/* Level-over-time trend chart — needs 2+ sessions, renders nothing below that */}
      <TrendChart series={layer2.trend_series} />

      {/* Layer 3 — AI narrative */}
      {layer3 && (
        <div className="bg-cyan-500/8 border border-cyan-500/20 rounded-xl p-4 flex items-start gap-2.5">
          <Sparkles size={14} className="text-cyan-400 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <p className="text-[10px] text-cyan-400 uppercase tracking-wider font-semibold">Summary</p>
              {onRegenerate && (
                <button onClick={onRegenerate} disabled={!!regenerating}
                  title="Regenerate this summary — useful if it reads stale or off"
                  className="text-cyan-400/70 hover:text-cyan-300 transition-colors disabled:opacity-50 shrink-0">
                  {regenerating ? <Loader2 size={11} className="animate-spin" /> : <RotateCcw size={11} />}
                </button>
              )}
            </div>
            <p className="text-[var(--tx2)] text-sm leading-relaxed">{layer3.narrative}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TeacherStudentDetailPage() {
  const router       = useRouter();
  const params       = useParams();
  const searchParams = useSearchParams();
  const studentId    = params.id as string;
  const { user, token } = useSessionStore();
  const { t, tF } = useTranslation();

  // Where this page was navigated from (set by whoever links here) so the
  // back button actually returns there instead of always going to the
  // general students list, e.g. arriving from a course's progress page.
  const fromCourseId = searchParams.get('from') === 'progress' ? searchParams.get('courseId') : null;
  const backHref  = fromCourseId ? `/teacher/courses/${fromCourseId}/progress` : '/teacher/students';
  const backLabel = fromCourseId ? t.teacher.backToProgress : t.teacher.backToStudents;

  const KIND_LABEL: Record<string, { label: string; icon: typeof HelpCircle }> = {
    quiz:       { label: t.teacher.kindQuiz,       icon: HelpCircle },
    flashcards: { label: t.teacher.kindFlashcards, icon: Layers },
    video:      { label: t.teacher.kindVideo,      icon: Video },
    studyset:   { label: t.teacher.kindStudySet,   icon: BookOpen },
  };

  const [data,          setData]          = useState<StudentProgress | null>(null);
  const [profile,       setProfile]       = useState<Profile | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading,       setLoading]       = useState(true);

  const [expandedConvId,   setExpandedConvId]   = useState<string | null>(null);
  const [convMessages,     setConvMessages]     = useState<ChatMessage[]>([]);
  const [loadingMessages,  setLoadingMessages]  = useState(false);

  const [expandedQuizConcept, setExpandedQuizConcept] = useState<string | null>(null);
  const [quizHistories,       setQuizHistories]       = useState<Record<string, QuizAttempt[]>>({});
  const [loadingQuizHistory,  setLoadingQuizHistory]  = useState<string | null>(null);

  const [assignments,     setAssignments]     = useState<Assignment[]>([]);
  const [assigning,       setAssigning]       = useState<string | null>(null);
  const [expandedAssignmentId,   setExpandedAssignmentId]   = useState<string | null>(null);
  const [assignmentDetails,      setAssignmentDetails]      = useState<Record<string, AssignmentDetail>>({});
  const [assignmentActionLoading, setAssignmentActionLoading] = useState<string | null>(null);

  const [expandedSummaryCourse, setExpandedSummaryCourse] = useState<string | null>(null);
  const [courseSummaries, setCourseSummaries] = useState<Record<string, CourseSummary | 'loading' | null>>({});
  const [regeneratingCourse, setRegeneratingCourse] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'overview' | 'progress' | 'practice' | 'conversations'>('overview');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user, studentId]);

  async function load() {
    setLoading(true);
    try {
      const [progressRes, profileRes, convRes, assignRes] = await Promise.all([
        fetch(`${API_BASE}/api/students/${studentId}/progress`, { headers }),
        fetch(`${API_BASE}/api/students/${studentId}/profile`, { headers }),
        fetch(`${API_BASE}/api/students/${studentId}/conversations`, { headers }),
        fetch(`${API_BASE}/api/assignments/student/${studentId}`, { headers }),
      ]);
      if (!progressRes.ok) { router.replace('/teacher/students'); return; }
      const progress = await progressRes.json();
      setData(progress);
      if (profileRes.ok) setProfile(await profileRes.json());
      if (convRes.ok)    setConversations(await convRes.json());
      if (assignRes.ok)  setAssignments(await assignRes.json());
    } finally { setLoading(false); }
  }

  const refreshAssignments = useCallback(async () => {
    const r = await fetch(`${API_BASE}/api/assignments/student/${studentId}`, { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) setAssignments(await r.json());
  }, [studentId, token]);

  // While a teacher is watching this tab, poll for a generating assignment
  // to land in 'pending_review' on its own — same interval/pattern as
  // LadderReportModal's poll-while-pending.
  useEffect(() => {
    if (!assignments.some(a => a.status === 'generating')) return;
    const id = setInterval(refreshAssignments, 4000);
    return () => clearInterval(id);
  }, [assignments, refreshAssignments]);

  async function assign(conceptId: string, kind: string) {
    const key = `${conceptId}:${kind}`;
    setAssigning(key);
    try {
      const res = await fetch(`${API_BASE}/api/assignments`, {
        method: 'POST', headers,
        body: JSON.stringify({ student_id: studentId, concept_id: conceptId, kind }),
      });
      if (res.ok) await refreshAssignments();
    } finally { setAssigning(null); }
  }

  function forgetAssignmentDetail(id: string) {
    setAssignmentDetails(prev => {
      if (!(id in prev)) return prev;
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }

  async function toggleAssignment(id: string) {
    if (expandedAssignmentId === id) { setExpandedAssignmentId(null); return; }
    setExpandedAssignmentId(id);
    if (assignmentDetails[id]) return;
    const res = await fetch(`${API_BASE}/api/assignments/${id}`, { headers });
    if (res.ok) {
      const d: AssignmentDetail = await res.json();
      setAssignmentDetails(prev => ({ ...prev, [id]: d }));
    }
  }

  async function approveAssignment(id: string) {
    setAssignmentActionLoading(`${id}:approve`);
    try {
      await fetch(`${API_BASE}/api/assignments/${id}/review`, { method: 'POST', headers });
      forgetAssignmentDetail(id);
      setExpandedAssignmentId(prev => prev === id ? null : prev);
      await refreshAssignments();
    } finally { setAssignmentActionLoading(null); }
  }

  async function regenerateAssignment(id: string) {
    setAssignmentActionLoading(`${id}:regenerate`);
    try {
      await fetch(`${API_BASE}/api/assignments/${id}/regenerate`, { method: 'POST', headers });
      forgetAssignmentDetail(id);
      setExpandedAssignmentId(prev => prev === id ? null : prev);
      await refreshAssignments();
    } finally { setAssignmentActionLoading(null); }
  }

  async function discardAssignment(id: string) {
    setAssignmentActionLoading(`${id}:discard`);
    try {
      await fetch(`${API_BASE}/api/assignments/${id}`, { method: 'DELETE', headers });
      forgetAssignmentDetail(id);
      setExpandedAssignmentId(prev => prev === id ? null : prev);
      await refreshAssignments();
    } finally { setAssignmentActionLoading(null); }
  }

  async function toggleQuizDrilldown(conceptId: string, hasAttempts: boolean) {
    if (expandedQuizConcept === conceptId) { setExpandedQuizConcept(null); return; }
    setExpandedQuizConcept(conceptId);
    if (quizHistories[conceptId] || !hasAttempts) return;
    setLoadingQuizHistory(conceptId);
    try {
      const res = await fetch(`${API_BASE}/api/students/${studentId}/concepts/${conceptId}/quiz-history`, { headers });
      if (res.ok) { const data = await res.json(); setQuizHistories(prev => ({ ...prev, [conceptId]: data })); }
    } finally { setLoadingQuizHistory(null); }
  }

  async function toggleCourseSummary(courseId: string) {
    if (expandedSummaryCourse === courseId) { setExpandedSummaryCourse(null); return; }
    setExpandedSummaryCourse(courseId);
    if (courseSummaries[courseId] && courseSummaries[courseId] !== 'loading') return;
    setCourseSummaries(prev => ({ ...prev, [courseId]: 'loading' }));
    try {
      const res  = await fetch(`${API_BASE}/api/students/${studentId}/courses/${courseId}/summary`, { headers });
      const data = res.ok ? await res.json() : null;
      setCourseSummaries(prev => ({ ...prev, [courseId]: data }));
    } catch {
      setCourseSummaries(prev => ({ ...prev, [courseId]: null }));
    }
  }

  async function regenerateCourseSummary(courseId: string) {
    setRegeneratingCourse(courseId);
    try {
      const res  = await fetch(`${API_BASE}/api/students/${studentId}/courses/${courseId}/summary?force=true`, { headers });
      const data = res.ok ? await res.json() : null;
      if (data) setCourseSummaries(prev => ({ ...prev, [courseId]: data }));
    } finally {
      setRegeneratingCourse(null);
    }
  }

  async function toggleConversation(convId: string) {
    if (expandedConvId === convId) { setExpandedConvId(null); return; }
    setExpandedConvId(convId);
    setLoadingMessages(true);
    try {
      const res = await fetch(`${API_BASE}/api/students/${studentId}/conversations/${convId}/messages`, { headers });
      setConvMessages(res.ok ? await res.json() : []);
    } finally { setLoadingMessages(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!data) return null;

  const atRiskCourses = data.courses.filter(isAtRisk);

  return (
    <div className="p-6 max-w-3xl mx-auto pb-16">
      <button onClick={() => router.push(backHref)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> {backLabel}
      </button>

      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-[var(--tx1)] text-2xl font-bold">{data.name ?? data.email}</h1>
            {atRiskCourses.length > 0 && (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
                <AlertTriangle size={11} /> At risk
              </span>
            )}
          </div>
          <p className="text-[var(--tx7)] text-sm">{data.email}</p>
        </div>
        <button onClick={() => router.push(`/messages/${studentId}`)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border border-[var(--bd)]
                     text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all shrink-0">
          <MessageSquare size={14} /> {t.teacher.messageBtn}
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 mb-5 border-b border-[var(--bd)]">
        {([
          ['overview',      t.teacher.tabOverview,      Brain],
          ['progress',      t.teacher.tabProgress,      Footprints],
          ['practice',      t.teacher.tabPractice,      Sparkles],
          ['conversations', t.teacher.tabConversations, MessageSquare],
        ] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === key
                ? 'border-purple-500 text-purple-400'
                : 'border-transparent text-[var(--tx7)] hover:text-[var(--tx2)]'
            }`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
            <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Brain size={12} /> {t.teacher.learningProfileLabel}
            </h2>
            {!profile?.has_profile ? (
              <p className="text-[var(--tx7)] text-sm">{t.teacher.noProfileYet}</p>
            ) : (
              <div className="space-y-3">
                {Object.keys(profile.skill_scores).length > 0 && (
                  <div className="space-y-1.5">
                    {Object.entries(profile.skill_scores).map(([subject, score]) => (
                      <div key={subject} className="flex items-center gap-2 text-xs">
                        <span className="w-28 text-[var(--tx6)] truncate shrink-0">{subject}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-[var(--ov3)] overflow-hidden">
                          <div className={`h-full rounded-full ${score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-amber-500' : 'bg-red-500'}`}
                            style={{ width: `${score}%` }} />
                        </div>
                        <span className="text-[var(--tx6)] w-8 text-right shrink-0">{Math.round(score)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {profile.struggle_areas.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {profile.struggle_areas.map((a, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">{a}</span>
                    ))}
                  </div>
                )}
                {profile.known_misconceptions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {profile.known_misconceptions.map((m, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">{m}</span>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-3 text-xs text-[var(--tx7)]">
                  {profile.grade && <span>Grade: {profile.grade}</span>}
                  {profile.goal  && <span>Goal: {profile.goal}</span>}
                  <span>{profile.total_messages} AI messages</span>
                </div>
              </div>
            )}
          </div>

          {data.courses.map(course => {
            const risk = isAtRisk(course);
            return (
              <div key={course.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-[var(--tx1)] font-semibold flex-1">{course.name}</h2>
                  {risk && (
                    <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <AlertTriangle size={9} /> {t.teacher.needsAttention}
                    </span>
                  )}
                </div>

                <div className="mb-4">
                  <MasteryBar concepts={course.concepts} />
                </div>

                <button
                  onClick={() => toggleCourseSummary(course.id)}
                  className="w-full flex items-center justify-between gap-2 text-xs px-3 py-2 rounded-lg border border-cyan-500/30 bg-cyan-500/5 text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                >
                  <span className="flex items-center gap-1.5 font-medium"><Sparkles size={12} /> Complete Result</span>
                  {expandedSummaryCourse === course.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
                {expandedSummaryCourse === course.id && (
                  <div className="mt-3 border border-[var(--bd)] rounded-xl p-4 bg-[var(--ov1)]">
                    {courseSummaries[course.id] === 'loading' ? (
                      <div className="flex flex-col items-center justify-center gap-2 py-6">
                        <Loader2 size={18} className="text-cyan-400 animate-spin" />
                        <p className="text-[var(--tx8)] text-[10px]">Rolling up progress and writing the summary — a few seconds…</p>
                      </div>
                    ) : courseSummaries[course.id] ? (
                      <CourseSummaryPanel
                        summary={courseSummaries[course.id] as CourseSummary}
                        onRegenerate={() => regenerateCourseSummary(course.id)}
                        regenerating={regeneratingCourse === course.id}
                      />
                    ) : (
                      <p className="text-[var(--tx7)] text-xs text-center py-4">Could not load the summary — try again.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Practice tab — per-concept, ladder-informed */}
      {activeTab === 'practice' && (
        <div className="space-y-4">
          {data.courses.length === 0 ? (
            <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
              <p className="text-[var(--tx6)] text-sm">{t.teacher.noConceptsToAssign}</p>
            </div>
          ) : (
            (() => {
              const order: Record<Mastery, number> = { struggling: 0, practiced: 1, visited: 2, mastered: 3, none: 4 };
              const coursesWithVisited = data.courses
                .map(c => ({ course: c, visited: [...c.concepts.filter(cc => cc.visited)].sort((a, b) => order[getMastery(a)] - order[getMastery(b)]) }))
                .filter(x => x.visited.length > 0);
              if (coursesWithVisited.length === 0) {
                return <p className="text-[var(--tx7)] text-sm text-center py-6">{t.teacher.practiceNoVisited}</p>;
              }
              return coursesWithVisited.map(({ course, visited }) => (
                <div key={course.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
                  <h2 className="text-[var(--tx1)] font-semibold mb-3">{course.name}</h2>
                  <div className="space-y-3">
                    {visited.map(concept => {
                      const m = getMastery(concept);
                      const conceptAssignments = assignments.filter(a => a.concept_id === concept.id);
                      const lr = concept.ladder_report;
                      return (
                        <div key={concept.id} className="border border-[var(--bd)] rounded-xl p-3.5">
                          <div className="flex items-center gap-2 mb-2">
                            {m === 'mastered'   && <CheckCircle2 size={13} className="text-green-400 shrink-0" />}
                            {m === 'practiced'  && <CheckCircle2 size={13} className="text-amber-400 shrink-0" />}
                            {m === 'struggling' && <AlertTriangle size={13} className="text-red-400 shrink-0" />}
                            {m === 'visited'    && <Circle size={13} className="text-blue-400 shrink-0" />}
                            <span className="text-sm font-medium text-[var(--tx1)] flex-1 truncate">{concept.title}</span>
                          </div>

                          {lr && m === 'mastered' && lr.optional_extension ? (
                            <p className="text-xs text-cyan-400 mb-2.5 flex items-start gap-1.5">
                              <Sparkles size={11} className="shrink-0 mt-0.5" />
                              <span>{t.teacher.practiceReadyForMore}: {lr.optional_extension}</span>
                            </p>
                          ) : lr && lr.weak_dimension ? (
                            <div className="mb-2.5">
                              <p className="text-xs text-amber-400 flex items-center gap-1">
                                <Target size={11} />
                                {tF(t.teacher.practiceFocusLabel, { dim: lr.weak_dimension, level: lr.weak_level || '' })}
                              </p>
                              {lr.next_growth_step && (
                                <p className="text-[11px] text-[var(--tx7)] mt-0.5 ml-4">{lr.next_growth_step}</p>
                              )}
                            </div>
                          ) : null}

                          <div className="flex gap-2 flex-wrap">
                            {Object.entries(KIND_LABEL).map(([kind, { label, icon: Icon }]) => {
                              const key = `${concept.id}:${kind}`;
                              const isDisabled = DISABLED_ASSIGN_KINDS.has(kind);
                              const isRecommended = concept.recommended_kind === kind && !isDisabled;
                              return (
                                <button key={kind} onClick={() => assign(concept.id, kind)}
                                  disabled={isDisabled || assigning === key}
                                  title={isDisabled ? t.teacher.comingSoon : isRecommended ? (concept.recommend_reason || undefined) : undefined}
                                  className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border transition-all ${
                                    isDisabled
                                      ? 'opacity-40 cursor-not-allowed border-[var(--bd)] text-[var(--tx8)]'
                                      : 'disabled:opacity-50 ' + (isRecommended
                                          ? 'border-purple-500/50 bg-purple-500/10 text-purple-300 hover:bg-purple-500/15'
                                          : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400')
                                  }`}>
                                  {assigning === key ? <Loader2 size={14} className="animate-spin" /> : isRecommended ? <Star size={13} className="fill-purple-400 text-purple-400" /> : <Icon size={14} />}
                                  {label}
                                  {isRecommended && <span className="text-[9px] uppercase tracking-wide opacity-80">{t.teacher.practiceRecommended}</span>}
                                </button>
                              );
                            })}
                          </div>

                          {conceptAssignments.length > 0 && (
                            <div className="mt-2.5 pt-2.5 border-t border-[var(--bd)] space-y-1.5">
                              {conceptAssignments.map(a => {
                                const meta = KIND_LABEL[a.kind];
                                const isExpanded = expandedAssignmentId === a.id;
                                const canExpand = a.status === 'pending_review' || (a.status === 'ready' && a.kind === 'quiz' && a.score !== null);
                                const adetail = assignmentDetails[a.id];
                                const busy = assignmentActionLoading?.startsWith(`${a.id}:`);
                                return (
                                  <div key={a.id} className="rounded-lg border border-[var(--bd)] overflow-hidden">
                                    <button onClick={() => canExpand && toggleAssignment(a.id)} disabled={!canExpand}
                                      className={`w-full flex items-center gap-2 text-xs px-2.5 py-2 text-left transition-colors ${canExpand ? 'hover:bg-[var(--ov1)]' : 'cursor-default'}`}>
                                      {meta && <meta.icon size={11} className="text-[var(--tx7)] shrink-0" />}
                                      <span className="flex-1 text-[var(--tx2)] truncate">{a.title}</span>
                                      {a.status === 'generating' && <span className="text-amber-400 flex items-center gap-1 shrink-0"><Loader2 size={10} className="animate-spin" /> {t.teacher.assignmentGenerating}</span>}
                                      {a.status === 'pending_review' && <span className="text-cyan-400 shrink-0">{t.teacher.assetReadyReview}</span>}
                                      {a.status === 'ready' && a.kind === 'quiz' && a.score !== null && <span className="text-green-400 shrink-0">{tF(t.teacher.assignmentScored, { pct: Math.round(a.score) })}</span>}
                                      {a.status === 'ready' && a.kind === 'quiz' && a.score === null && <span className="text-[var(--tx7)] shrink-0">{t.teacher.notAttemptedYet}</span>}
                                      {a.status === 'ready' && a.kind !== 'quiz' && <span className="text-green-400 shrink-0">{t.teacher.assignmentReady}</span>}
                                      {a.status === 'failed' && <span className="text-red-400 flex items-center gap-1 shrink-0"><AlertTriangle size={10} /> {t.teacher.assignmentFailed}</span>}
                                      {canExpand && (isExpanded ? <ChevronUp size={11} className="text-[var(--tx7)] shrink-0" /> : <ChevronDown size={11} className="text-[var(--tx7)] shrink-0" />)}
                                    </button>

                                    {a.status === 'failed' && (
                                      <div className="px-2.5 pb-2 flex justify-end">
                                        <button onClick={() => discardAssignment(a.id)} disabled={!!busy}
                                          className="text-[10px] text-[var(--tx7)] hover:text-red-400 transition-colors disabled:opacity-50">
                                          {t.delete}
                                        </button>
                                      </div>
                                    )}

                                    {isExpanded && (
                                      <div className="border-t border-[var(--bd)] p-3 bg-[var(--ov1)]">
                                        {!adetail ? (
                                          <Loader2 size={14} className="animate-spin text-[var(--tx7)] mx-auto block" />
                                        ) : a.status === 'pending_review' ? (
                                          <div className="space-y-3">
                                            {a.kind === 'quiz' && adetail.payload && (
                                              <div className="space-y-2.5">
                                                {(adetail.payload as AssignmentQuizQuestion[]).map((q, qi) => (
                                                  <div key={qi} className="text-xs">
                                                    <p className="text-[var(--tx1)] font-medium mb-1">{qi + 1}. {q.question}</p>
                                                    <div className="space-y-0.5 ml-3">
                                                      {q.options.map((opt, oi) => (
                                                        <p key={oi} className={oi === q.correct_idx ? 'text-green-400' : 'text-[var(--tx7)]'}>
                                                          {oi === q.correct_idx ? '✓ ' : '· '}{opt}
                                                        </p>
                                                      ))}
                                                    </div>
                                                  </div>
                                                ))}
                                              </div>
                                            )}
                                            {a.kind === 'flashcards' && adetail.payload && (
                                              <div className="grid sm:grid-cols-2 gap-2">
                                                {(adetail.payload as AssignmentFlashcard[]).map((c, i) => (
                                                  <div key={i} className="text-xs border border-[var(--bd)] rounded-lg p-2 bg-[var(--surface)]">
                                                    <p className="text-[var(--tx1)] font-medium">{c.front}</p>
                                                    <p className="text-[var(--tx7)] mt-1">{c.back}</p>
                                                  </div>
                                                ))}
                                              </div>
                                            )}
                                            <div className="flex items-center gap-2 pt-1">
                                              <button onClick={() => approveAssignment(a.id)} disabled={!!assignmentActionLoading}
                                                className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 hover:bg-green-500/15 transition-colors disabled:opacity-50">
                                                {assignmentActionLoading === `${a.id}:approve` ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
                                                {t.teacher.approveBtn}
                                              </button>
                                              <button onClick={() => regenerateAssignment(a.id)} disabled={!!assignmentActionLoading}
                                                className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-colors disabled:opacity-50">
                                                {assignmentActionLoading === `${a.id}:regenerate` ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                                                {t.teacher.redoBtn}
                                              </button>
                                              <button onClick={() => discardAssignment(a.id)} disabled={!!assignmentActionLoading}
                                                className="text-xs px-2.5 py-1.5 rounded-lg border border-[var(--bd)] text-[var(--tx7)] hover:border-red-500/40 hover:text-red-400 transition-colors disabled:opacity-50">
                                                {t.delete}
                                              </button>
                                            </div>
                                          </div>
                                        ) : a.status === 'ready' && a.kind === 'quiz' && adetail.answers && adetail.payload ? (
                                          <div className="space-y-3">
                                            {(adetail.payload as AssignmentQuizQuestion[]).map((q, qi) => {
                                              const ans = adetail.answers!.find(x => x.qi === qi);
                                              const chosen = ans?.chosen;
                                              return (
                                                <div key={qi} className="text-xs">
                                                  <p className="text-[var(--tx1)] font-medium mb-1.5">{qi + 1}. {q.question}</p>
                                                  <div className="space-y-1">
                                                    {q.options.map((opt, oi) => {
                                                      const isCorrect = oi === q.correct_idx;
                                                      const isChosenWrong = oi === chosen && !isCorrect;
                                                      return (
                                                        <p key={oi} className={`flex items-center gap-1.5 ${isCorrect ? 'text-green-400' : isChosenWrong ? 'text-red-400' : 'text-[var(--tx7)]'}`}>
                                                          {isCorrect ? <CheckCircle2 size={11} className="shrink-0" />
                                                            : isChosenWrong ? <XCircle size={11} className="shrink-0" />
                                                            : <span className="w-[11px] shrink-0" />}
                                                          {opt}
                                                        </p>
                                                      );
                                                    })}
                                                  </div>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        ) : null}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ));
            })()
          )}
        </div>
      )}

      {/* Conversations tab */}
      {activeTab === 'conversations' && (
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-4">
        <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <MessageSquare size={12} /> {t.teacher.aiConversations}
        </h2>
        {conversations.length === 0 ? (
          <p className="text-[var(--tx7)] text-sm">{t.teacher.noAiConversations}</p>
        ) : (
          <div className="space-y-2">
            {conversations.map(c => (
              <div key={c.id} className="border border-[var(--bd)] rounded-xl overflow-hidden">
                <button onClick={() => toggleConversation(c.id)}
                  className="w-full flex items-center justify-between gap-3 p-3 text-left hover:bg-[var(--ov1)] transition-colors">
                  <div className="min-w-0">
                    <p className="text-[var(--tx1)] text-sm font-medium truncate">{c.title || t.teacher.untitledConversation}</p>
                    <p className="text-[var(--tx7)] text-xs">
                      {c.subject && `${c.subject} · `}{tF(t.teacher.messagesCount, { n: c.message_count })}
                      {c.last_message_at && ` · ${new Date(c.last_message_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  {expandedConvId === c.id ? <ChevronUp size={14} className="text-[var(--tx7)] shrink-0" /> : <ChevronDown size={14} className="text-[var(--tx7)] shrink-0" />}
                </button>
                {expandedConvId === c.id && (
                  <div className="border-t border-[var(--bd)] p-3 space-y-2 max-h-80 overflow-y-auto bg-[var(--ov1)]">
                    {loadingMessages ? (
                      <Loader2 size={16} className="animate-spin text-[var(--tx7)] mx-auto" />
                    ) : convMessages.map((m, i) => (
                      <div key={i} className={`text-xs p-2 rounded-lg max-w-[85%] ${
                        m.role === 'user' ? 'bg-purple-500/10 text-[var(--tx2)] ml-auto' : 'bg-[var(--ov2)] text-[var(--tx2)]'
                      }`}>
                        {m.content}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      )}

      {/* Progress tab — per-concept detail */}
      {activeTab === 'progress' && (
      data.courses.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">{t.teacher.noCoursesAssigned}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.courses.map(course => {
            return (
              <div key={course.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
                <h2 className="text-[var(--tx1)] font-semibold mb-3">{course.name}</h2>

                <div className="mb-4">
                  <MasteryBar concepts={course.concepts} />
                </div>

                {/* Per-concept rows */}
                <div className="space-y-1">
                  {course.concepts.map(concept => {
                    const m = getMastery(concept);
                    const isExpanded  = expandedQuizConcept === concept.id;
                    const history     = quizHistories[concept.id];
                    const isLoading   = loadingQuizHistory === concept.id;
                    const lastAnswers = concept.last_attempt_answers;
                    const hasQuiz     = concept.quiz_attempts.length > 0;
                    return (
                      <div key={concept.id} className="rounded-lg">
                        {/* ── Main row ── */}
                        <div className="flex items-center gap-3 text-sm py-1.5 px-1 rounded-lg hover:bg-[var(--ov1)]">
                          {/* Mastery icon */}
                          <div className="shrink-0">
                            {m === 'mastered'   && <CheckCircle2 size={14} className="text-green-400" />}
                            {m === 'practiced'  && <CheckCircle2 size={14} className="text-amber-400" />}
                            {m === 'struggling' && <AlertTriangle size={14} className="text-red-400" />}
                            {m === 'visited'    && <Circle size={14} className="text-blue-400" />}
                            {m === 'none'       && <Circle size={14} className="text-[var(--tx8)]" />}
                          </div>

                          {/* Title */}
                          <span className="flex-1 text-[var(--tx2)] truncate">{concept.title}</span>

                          {/* AI chat count */}
                          {concept.ai_msg_count > 0 && (
                            <span className="flex items-center gap-0.5 text-[10px] text-[var(--tx7)] shrink-0">
                              <MessageSquare size={9} /> {concept.ai_msg_count}
                            </span>
                          )}

                          {/* Flashcard mastery */}
                          {concept.flashcard_total > 0 && (
                            <span className={`text-[10px] shrink-0 ${
                              concept.flashcard_pct !== null && concept.flashcard_pct >= 70 ? 'text-green-400'
                              : concept.flashcard_pct !== null && concept.flashcard_pct >= 40 ? 'text-amber-400'
                              : 'text-[var(--tx7)]'
                            }`}>
                              <Layers size={9} className="inline mr-0.5" />
                              {concept.flashcard_mastered}/{concept.flashcard_total}
                            </span>
                          )}

                          {/* Time spent */}
                          {concept.time_spent_seconds > 0 && (
                            <span className="flex items-center gap-0.5 text-[10px] text-[var(--tx8)] shrink-0">
                              <Clock size={9} /> {formatTime(concept.time_spent_seconds)}
                            </span>
                          )}

                          {/* Videos watched */}
                          {concept.video_blocks_total > 0 && (
                            <span className={`flex items-center gap-0.5 text-[10px] shrink-0 ${
                              concept.video_blocks_watched === concept.video_blocks_total ? 'text-green-400'
                              : concept.video_blocks_watched > 0 ? 'text-amber-400'
                              : 'text-[var(--tx8)]'
                            }`}>
                              <Video size={9} /> {concept.video_blocks_watched}/{concept.video_blocks_total}
                            </span>
                          )}

                          {/* Last seen */}
                          {concept.last_seen_at && (
                            <span className="flex items-center gap-0.5 text-[10px] text-[var(--tx8)] shrink-0">
                              {relativeTime(concept.last_seen_at, t.teacher)}
                            </span>
                          )}

                          {/* Quiz score trend — clickable to expand full history */}
                          {hasQuiz ? (
                            <button
                              onClick={() => toggleQuizDrilldown(concept.id, true)}
                              className="flex items-center gap-1 shrink-0 hover:opacity-70 transition-opacity"
                            >
                              <QuizTrend attempts={concept.quiz_attempts} />
                              {isExpanded ? <ChevronUp size={10} className="text-[var(--tx7)]" /> : <ChevronDown size={10} className="text-[var(--tx7)]" />}
                            </button>
                          ) : null}
                        </div>

                        {/* ── Inline Q dots from last attempt ── */}
                        {lastAnswers && lastAnswers.length > 0 && (
                          <div className="ml-[22px] flex items-center gap-1 pb-1.5 flex-wrap">
                            {lastAnswers.map((ans, i) => (
                              <span
                                key={i}
                                title={`Q${i + 1}: ${ans.question} — ${ans.ok ? 'Correct' : `Wrong (chose ${String.fromCharCode(65 + ans.chosen)})`}`}
                                className={`w-2 h-2 rounded-full cursor-default ${ans.ok ? 'bg-green-400' : 'bg-red-400'}`}
                              />
                            ))}
                            <span className="text-[9px] text-[var(--tx8)] ml-1">{t.teacher.quizLastAttempt}</span>
                          </div>
                        )}

                        {/* Quiz drilldown — full attempt history on click */}
                        {isExpanded && (
                          <div className="ml-6 mr-1 mb-2 bg-[var(--ov1)] rounded-xl border border-[var(--bd)] overflow-hidden">
                            {isLoading ? (
                              <div className="flex items-center justify-center py-4">
                                <Loader2 size={16} className="text-purple-400 animate-spin" />
                              </div>
                            ) : !history || history.length === 0 ? (
                              <p className="text-[var(--tx7)] text-xs text-center py-3">{t.teacher.quizHistoryNoDetail}</p>
                            ) : (
                              <div className="divide-y divide-[var(--bd)]">
                                {history.map((attempt, ai) => (
                                  <div key={attempt.id} className="p-3">
                                    <div className="flex items-center gap-2 mb-2">
                                      <span className="text-[10px] text-[var(--tx7)] font-mono">{tF(t.teacher.quizHistoryAttempt, { n: ai + 1 })}</span>
                                      <span className={`text-[10px] font-semibold ${attempt.score >= 70 ? 'text-green-400' : attempt.score >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
                                        {attempt.score}%
                                      </span>
                                      {attempt.taken_at && (
                                        <span className="text-[10px] text-[var(--tx8)] ml-auto">
                                          {new Date(attempt.taken_at).toLocaleDateString()}
                                        </span>
                                      )}
                                    </div>
                                    {attempt.answers && attempt.answers.length > 0 ? (
                                      <div className="space-y-1">
                                        {attempt.answers.map(ans => (
                                          <div key={ans.qi} className={`flex items-start gap-1.5 text-[10px] rounded px-2 py-1 ${ans.ok ? 'bg-green-500/8 text-green-400' : 'bg-red-500/8 text-red-400'}`}>
                                            <span className="shrink-0 mt-0.5">{ans.ok ? '✓' : '✗'}</span>
                                            <span className="text-[var(--tx6)] flex-1 line-clamp-2">{ans.question}</span>
                                            {!ans.ok && (
                                              <span className="shrink-0 text-[var(--tx7)]">
                                                {tF(t.teacher.quizHistoryChose, { letter: String.fromCharCode(65 + ans.chosen) })}
                                              </span>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    ) : (
                                      <p className="text-[10px] text-[var(--tx8)]">{t.teacher.quizHistoryNoAnswers}</p>
                                    )}
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
            );
          })}
        </div>
      ))}
    </div>
  );
}
