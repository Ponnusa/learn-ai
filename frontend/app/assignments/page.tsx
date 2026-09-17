'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Sparkles, Loader2, HelpCircle, Layers, Video, BookOpen, AlertTriangle,
  ChevronDown, ChevronUp, CheckCircle2, XCircle,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { MathText } from '@/components/ui/MathText';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface AssignmentSummary {
  id: string; concept_id: string | null; kind: string; title: string; status: string; created_at: string | null;
  score: number | null; course_name: string | null;
}
interface QuizQuestion { question: string; options: string[]; correct_idx: number; explanation?: string; }
interface Flashcard    { front: string; back: string; }
interface SubmittedAnswer { qi: number; question: string; chosen: number; correct: number; ok: boolean; }
interface AssignmentDetail {
  id: string; kind: string; title: string; status: string;
  error_message: string | null; video_stage: string | null; video_url: string | null;
  payload: QuizQuestion[] | Flashcard[] | null; study_set_id: string | null;
  score: number | null; answers: SubmittedAnswer[] | null; course_name: string | null;
}

export default function AssignmentsPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();
  const { t, tF } = useTranslation();

  const KIND_LABEL: Record<string, { label: string; icon: typeof HelpCircle }> = {
    quiz:       { label: t.assignments.kindQuiz,       icon: HelpCircle },
    flashcards: { label: t.assignments.kindFlashcards, icon: Layers },
    video:      { label: t.assignments.kindVideo,      icon: Video },
    studyset:   { label: t.assignments.kindStudySet,   icon: BookOpen },
  };
  const VIDEO_STAGE_LABEL: Record<string, string> = {
    pending:          t.assignments.stageWriting,
    transcript_ready: t.assignments.stageAnimation,
    queued:           t.assignments.stageQueued,
    rendering:        t.assignments.stageRendering,
  };

  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [loading,      setLoading]    = useState(true);
  const [expandedId,   setExpandedId] = useState<string | null>(null);
  const [detail,       setDetail]     = useState<AssignmentDetail | null>(null);
  const [quizAnswers,  setQuizAnswers] = useState<Record<number, number>>({});
  const [submitted,    setSubmitted]  = useState(false);
  const [submittedPct, setSubmittedPct] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const headers = { Authorization: `Bearer ${token}` };
  const jsonHeaders = { ...headers, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    load();
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, [user]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/assignments/mine`, { headers });
      if (res.ok) setAssignments(await res.json());
    } finally { setLoading(false); }
  }

  async function toggle(id: string) {
    if (expandedId === id) { setExpandedId(null); setDetail(null); return; }
    setExpandedId(id);
    setQuizAnswers({});
    setSubmitted(false);
    setSubmittedPct(null);
    await fetchDetail(id);
  }

  async function submitQuizAttempt(payload: QuizQuestion[], answers: Record<number, number>) {
    const answerList = payload.map((q, qi) => ({
      qi, question: q.question, chosen: answers[qi], correct: q.correct_idx, ok: answers[qi] === q.correct_idx,
    }));
    const score = Math.round((answerList.filter(a => a.ok).length / payload.length) * 100);
    setSubmitted(true);
    setSubmittedPct(score);
    if (!expandedId) return;
    try {
      await fetch(`${API_BASE}/api/assignments/${expandedId}/submit`, {
        method: 'POST', headers: jsonHeaders,
        body: JSON.stringify({ score, answers: answerList }),
      });
    } catch { /* the student's own view already reflects the result either way */ }
  }

  async function fetchDetail(id: string) {
    const res = await fetch(`${API_BASE}/api/assignments/${id}`, { headers });
    if (!res.ok) return;
    const data: AssignmentDetail = await res.json();
    setDetail(data);
    setAssignments(prev => prev.map(a => a.id === id ? { ...a, status: data.status, score: data.score } : a));
    // A quiz already attempted (survives a refresh — this is read straight
    // back from the server, not just kept in local state) restores as
    // already-answered and locked, rather than a blank retake.
    if (data.kind === 'quiz' && data.answers) {
      const restored: Record<number, number> = {};
      data.answers.forEach(a => { restored[a.qi] = a.chosen; });
      setQuizAnswers(restored);
      setSubmitted(true);
      setSubmittedPct(data.score !== null ? Math.round(data.score) : null);
    }
    if (data.status === 'generating') {
      pollRef.current = setTimeout(() => fetchDetail(id), 4000);
    }
  }

  // Once every question in an assigned quiz has been answered, record the
  // attempt — previously this was graded purely client-side and the
  // teacher had no way to see whether a student even opened it. Triggered
  // directly from the click that completes the quiz rather than an effect
  // watching quizAnswers, since the action belongs with the event that
  // causes it, not as a reaction to state already having changed.
  function answerQuestion(qi: number, oi: number) {
    if (submitted) return; // one attempt only — also enforced server-side
    const next = { ...quizAnswers, [qi]: oi };
    setQuizAnswers(next);
    if (detail?.status === 'ready' && detail.kind === 'quiz' && detail.payload) {
      const payload = detail.payload as QuizQuestion[];
      if (Object.keys(next).length === payload.length) submitQuizAttempt(payload, next);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <MobileTopBar />
        <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex-1 flex items-center justify-center h-full">
            <Loader2 size={28} className="text-purple-400 animate-spin" />
          </div>
        ) : (
    <div className="p-6 max-w-2xl mx-auto pb-16">
      <div className="mb-6">
        <h1 className="text-[var(--tx1)] text-2xl font-bold flex items-center gap-2">
          <Sparkles size={20} className="text-purple-400" /> {t.assignments.title}
        </h1>
        <p className="text-[var(--tx6)] text-sm mt-1">{t.assignments.subtitle}</p>
      </div>

      {assignments.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-[var(--tx3)] font-medium mb-1">{t.assignments.noAssignments}</p>
          <p className="text-[var(--tx7)] text-sm">{t.assignments.noAssignmentsHint}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {assignments.map(a => {
            const meta = KIND_LABEL[a.kind];
            return (
              <div key={a.id} className="border border-[var(--bd)] rounded-2xl overflow-hidden bg-[var(--surface)]">
                <button onClick={() => toggle(a.id)}
                  className="w-full flex items-center gap-3 p-4 text-left hover:bg-[var(--ov1)] transition-colors">
                  {meta && <meta.icon size={16} className="text-purple-400 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--tx1)] text-sm font-medium truncate">{a.title}</p>
                    <p className="text-[var(--tx7)] text-xs">{meta?.label ?? a.kind}</p>
                  </div>
                  {a.status === 'generating' && <Loader2 size={14} className="animate-spin text-amber-400 shrink-0" />}
                  {a.status === 'failed'     && <AlertTriangle size={14} className="text-red-400 shrink-0" />}
                  {a.status === 'ready' && a.kind === 'quiz' && a.score !== null && (
                    <span className="text-xs text-green-400 flex items-center gap-1 shrink-0">
                      <CheckCircle2 size={13} /> {Math.round(a.score)}%
                    </span>
                  )}
                  {expandedId === a.id ? <ChevronUp size={14} className="text-[var(--tx7)] shrink-0" /> : <ChevronDown size={14} className="text-[var(--tx7)] shrink-0" />}
                </button>

                {expandedId === a.id && detail && (
                  <div className="border-t border-[var(--bd)] p-4">
                    {(detail.course_name || a.title) && (
                      <p className="text-[var(--tx7)] text-xs mb-3">
                        {detail.course_name}{detail.course_name && a.title ? ' › ' : ''}{a.title}
                      </p>
                    )}
                    {detail.status === 'generating' && (
                      <p className="text-[var(--tx7)] text-sm flex items-center gap-2">
                        <Loader2 size={14} className="animate-spin" />
                        {detail.kind === 'video' && detail.video_stage
                          ? (VIDEO_STAGE_LABEL[detail.video_stage] ?? t.assignments.generating)
                          : t.assignments.generating}
                      </p>
                    )}
                    {detail.status === 'failed' && (
                      <p className="text-red-400 text-sm">{detail.error_message ?? t.assignments.generationFailed}</p>
                    )}

                    {detail.status === 'ready' && detail.kind === 'quiz' && (
                      <div className="space-y-4">
                        {submitted && submittedPct !== null && (
                          <p className="text-sm text-green-400 flex items-center gap-1.5 bg-green-500/8 border border-green-500/20 rounded-xl px-3 py-2">
                            <CheckCircle2 size={14} className="shrink-0" />
                            {tF(t.assignments.submittedScore, { pct: submittedPct })}
                          </p>
                        )}
                        {(detail.payload as QuizQuestion[]).map((q, qi) => {
                          const chosen = quizAnswers[qi];
                          const answered = chosen !== undefined;
                          return (
                            <div key={qi}>
                              <p className="text-[var(--tx1)] text-sm font-medium mb-2">{qi + 1}. <MathText inline>{q.question}</MathText></p>
                              <div className="space-y-1.5">
                                {q.options.map((opt, oi) => {
                                  let cls = 'bg-[var(--ov1)] border-[var(--bd)] text-[var(--tx2)]';
                                  if (answered) {
                                    if (oi === q.correct_idx) cls = 'bg-green-500/15 border-green-500/40 text-green-400';
                                    else if (oi === chosen)   cls = 'bg-red-500/15 border-red-500/40 text-red-400';
                                    else                       cls = 'bg-[var(--ov1)] border-[var(--bd)] text-[var(--tx7)] opacity-60';
                                  }
                                  return (
                                    <button key={oi} disabled={answered}
                                      onClick={() => answerQuestion(qi, oi)}
                                      className={`w-full text-left flex items-center gap-2 px-3 py-2 border rounded-xl text-sm transition-all ${cls}`}>
                                      <span className="flex-1"><MathText inline>{opt}</MathText></span>
                                      {answered && oi === q.correct_idx && <CheckCircle2 size={13} className="text-green-400 shrink-0" />}
                                      {answered && oi === chosen && oi !== q.correct_idx && <XCircle size={13} className="text-red-400 shrink-0" />}
                                    </button>
                                  );
                                })}
                              </div>
                              {answered && q.explanation && (
                                <p className="text-[var(--tx6)] text-xs mt-1.5"><MathText inline>{q.explanation}</MathText></p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {detail.status === 'ready' && detail.kind === 'flashcards' && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {(detail.payload as Flashcard[]).map((c, i) => (
                          <FlipCard key={i} front={c.front} back={c.back} />
                        ))}
                      </div>
                    )}

                    {detail.status === 'ready' && detail.kind === 'studyset' && detail.study_set_id && (
                      <button onClick={() => router.push(`/study/${detail.study_set_id}`)}
                        className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-xl transition-all">
                        {t.assignments.openStudySet}
                      </button>
                    )}

                    {detail.status === 'ready' && detail.kind === 'video' && detail.video_url && (
                      <video controls controlsList="nodownload" disablePictureInPicture
                        src={detail.video_url} className="w-full aspect-video rounded-xl"
                        onContextMenu={e => e.preventDefault()} />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
        )}
        </div>
      </main>
    </div>
  );
}

function FlipCard({ front, back }: { front: string; back: string }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <div onClick={() => setFlipped(f => !f)}
      className="bg-[var(--ov1)] border border-[var(--bd)] rounded-xl p-3 min-h-[80px] flex items-center justify-center text-center cursor-pointer">
      <p className="text-sm text-[var(--tx2)]"><MathText inline>{flipped ? back : front}</MathText></p>
    </div>
  );
}
