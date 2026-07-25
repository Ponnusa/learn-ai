'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Loader2, Brain, MessageSquare, ChevronDown, ChevronUp,
  Sparkles, HelpCircle, Layers, Video, BookOpen, AlertTriangle,
  CheckCircle2, Circle, Clock, Zap,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ConceptProgress {
  id: string; title: string;
  visited: boolean; quiz_score: number | null;
  last_seen_at: string | null;
  flashcard_pct: number | null;
  flashcard_mastered: number; flashcard_total: number;
  ai_msg_count: number;
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

interface Assignment {
  id: string; concept_id: string | null; kind: string;
  title: string; status: string; created_at: string | null;
}

type Mastery = 'none' | 'visited' | 'struggling' | 'practiced' | 'mastered';

function getMastery(c: ConceptProgress): Mastery {
  if (!c.visited) return 'none';
  if (c.quiz_score === null) return 'visited';
  if (c.quiz_score >= 70) return 'mastered';
  if (c.quiz_score >= 40) return 'practiced';
  return 'struggling';
}

function relativeTime(iso: string | null): string {
  if (!iso) return '—';
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days === 0) return 'today';
  if (days === 1) return '1d ago';
  if (days < 7)  return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
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

export default function TeacherStudentDetailPage() {
  const router    = useRouter();
  const params    = useParams();
  const studentId = params.id as string;
  const { user, token } = useSessionStore();
  const { t, tF } = useTranslation();

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

  const [assignments,     setAssignments]     = useState<Assignment[]>([]);
  const [selectedConcept, setSelectedConcept] = useState('');
  const [assigning,       setAssigning]       = useState<string | null>(null);

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
      if (!selectedConcept) {
        const first = progress.courses?.[0]?.concepts?.[0]?.id;
        if (first) setSelectedConcept(first);
      }
    } finally { setLoading(false); }
  }

  async function assign(kind: string) {
    if (!selectedConcept) return;
    setAssigning(kind);
    try {
      const res = await fetch(`${API_BASE}/api/assignments`, {
        method: 'POST', headers,
        body: JSON.stringify({ student_id: studentId, concept_id: selectedConcept, kind }),
      });
      if (res.ok) {
        const r = await fetch(`${API_BASE}/api/assignments/student/${studentId}`, { headers });
        if (r.ok) setAssignments(await r.json());
      }
    } finally { setAssigning(null); }
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
      <button onClick={() => router.push('/teacher/students')}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> {t.teacher.backToStudents}
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

      {/* Learning profile */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-4">
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

      {/* Assign extra practice */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-4">
        <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Sparkles size={12} /> {t.teacher.assignExtraPractice}
        </h2>
        {data.courses.length === 0 ? (
          <p className="text-[var(--tx7)] text-sm">{t.teacher.noConceptsToAssign}</p>
        ) : (
          <>
            <select value={selectedConcept} onChange={e => setSelectedConcept(e.target.value)}
              className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                         text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors mb-3">
              {data.courses.map(c => (
                <optgroup key={c.id} label={c.name}>
                  {c.concepts.map(concept => (
                    <option key={concept.id} value={concept.id}>{concept.title}</option>
                  ))}
                </optgroup>
              ))}
            </select>
            <div className="flex gap-2 flex-wrap">
              {Object.entries(KIND_LABEL).map(([kind, { label, icon: Icon }]) => (
                <button key={kind} onClick={() => assign(kind)} disabled={!!assigning}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border border-[var(--bd)]
                             text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all disabled:opacity-50">
                  {assigning === kind ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
                  {label}
                </button>
              ))}
            </div>
          </>
        )}
        {assignments.length > 0 && (
          <div className="mt-4 pt-4 border-t border-[var(--bd)] space-y-1.5">
            {assignments.map(a => {
              const meta = KIND_LABEL[a.kind];
              return (
                <div key={a.id} className="flex items-center gap-2 text-sm">
                  {meta && <meta.icon size={13} className="text-[var(--tx7)] shrink-0" />}
                  <span className="flex-1 text-[var(--tx2)] truncate">{a.title}</span>
                  {a.status === 'generating' && <span className="text-xs text-amber-400 flex items-center gap-1"><Loader2 size={11} className="animate-spin" /> {t.teacher.assignmentGenerating}</span>}
                  {a.status === 'ready'      && <span className="text-xs text-green-400">{t.teacher.assignmentReady}</span>}
                  {a.status === 'failed'     && <span className="text-xs text-red-400 flex items-center gap-1"><AlertTriangle size={11} /> {t.teacher.assignmentFailed}</span>}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* AI tutor conversations */}
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

      {/* Course progress — per-concept detail */}
      {data.courses.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">{t.teacher.noCoursesAssigned}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.courses.map(course => {
            const risk = isAtRisk(course);
            return (
              <div key={course.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-[var(--tx1)] font-semibold flex-1">{course.name}</h2>
                  {risk && (
                    <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <AlertTriangle size={9} /> Needs attention
                    </span>
                  )}
                </div>

                {/* Mastery progress bar */}
                <div className="mb-4">
                  <MasteryBar concepts={course.concepts} />
                </div>

                {/* Per-concept rows */}
                <div className="space-y-1">
                  {course.concepts.map(concept => {
                    const m = getMastery(concept);
                    return (
                      <div key={concept.id} className="flex items-center gap-3 text-sm py-1.5 px-1 rounded-lg hover:bg-[var(--ov1)]">
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

                        {/* Last seen */}
                        {concept.last_seen_at && (
                          <span className="flex items-center gap-0.5 text-[10px] text-[var(--tx8)] shrink-0">
                            <Clock size={9} /> {relativeTime(concept.last_seen_at)}
                          </span>
                        )}

                        {/* Quiz score */}
                        {concept.quiz_score !== null && (
                          <span className={`text-xs font-medium shrink-0 ${
                            concept.quiz_score >= 70 ? 'text-green-400'
                            : concept.quiz_score >= 40 ? 'text-amber-400'
                            : 'text-red-400'
                          }`}>{Math.round(concept.quiz_score)}%</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
