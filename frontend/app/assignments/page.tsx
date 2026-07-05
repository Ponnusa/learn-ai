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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface AssignmentSummary {
  id: string; concept_id: string | null; kind: string; title: string; status: string; created_at: string | null;
}
interface QuizQuestion { question: string; options: string[]; correct_idx: number; explanation?: string; }
interface Flashcard    { front: string; back: string; }
interface AssignmentDetail {
  id: string; kind: string; title: string; status: string;
  error_message: string | null; video_stage: string | null; video_url: string | null;
  payload: QuizQuestion[] | Flashcard[] | null; study_set_id: string | null;
}

const KIND_LABEL: Record<string, { label: string; icon: typeof HelpCircle }> = {
  quiz:       { label: 'Quiz',       icon: HelpCircle },
  flashcards: { label: 'Flashcards', icon: Layers },
  video:      { label: 'Video',      icon: Video },
  studyset:   { label: 'Study set',  icon: BookOpen },
};

const VIDEO_STAGE_LABEL: Record<string, string> = {
  pending:          'Writing the scene…',
  transcript_ready: 'Generating animation code…',
  queued:           'Queued for rendering…',
  rendering:        'Rendering animation…',
};

export default function AssignmentsPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();

  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [loading,      setLoading]    = useState(true);
  const [expandedId,   setExpandedId] = useState<string | null>(null);
  const [detail,       setDetail]     = useState<AssignmentDetail | null>(null);
  const [quizAnswers,  setQuizAnswers] = useState<Record<number, number>>({});
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const headers = { Authorization: `Bearer ${token}` };

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
    await fetchDetail(id);
  }

  async function fetchDetail(id: string) {
    const res = await fetch(`${API_BASE}/api/assignments/${id}`, { headers });
    if (!res.ok) return;
    const data: AssignmentDetail = await res.json();
    setDetail(data);
    setAssignments(prev => prev.map(a => a.id === id ? { ...a, status: data.status } : a));
    if (data.status === 'generating') {
      pollRef.current = setTimeout(() => fetchDetail(id), 4000);
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
          <Sparkles size={20} className="text-purple-400" /> Extra Practice
        </h1>
        <p className="text-[var(--tx6)] text-sm mt-1">Assigned by your teachers</p>
      </div>

      {assignments.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-[var(--tx3)] font-medium mb-1">No extra practice assigned yet</p>
          <p className="text-[var(--tx7)] text-sm">Your teacher can assign quizzes, flashcards, videos, or study sets here</p>
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
                  {expandedId === a.id ? <ChevronUp size={14} className="text-[var(--tx7)] shrink-0" /> : <ChevronDown size={14} className="text-[var(--tx7)] shrink-0" />}
                </button>

                {expandedId === a.id && detail && (
                  <div className="border-t border-[var(--bd)] p-4">
                    {detail.status === 'generating' && (
                      <p className="text-[var(--tx7)] text-sm flex items-center gap-2">
                        <Loader2 size={14} className="animate-spin" />
                        {detail.kind === 'video' && detail.video_stage
                          ? (VIDEO_STAGE_LABEL[detail.video_stage] ?? 'Generating…')
                          : 'Generating…'}
                      </p>
                    )}
                    {detail.status === 'failed' && (
                      <p className="text-red-400 text-sm">{detail.error_message ?? 'Generation failed — ask your teacher to try again.'}</p>
                    )}

                    {detail.status === 'ready' && detail.kind === 'quiz' && (
                      <div className="space-y-4">
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
                                      onClick={() => setQuizAnswers(p => ({ ...p, [qi]: oi }))}
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
                        Open study set
                      </button>
                    )}

                    {detail.status === 'ready' && detail.kind === 'video' && detail.video_url && (
                      <video controls src={detail.video_url} className="w-full aspect-video rounded-xl" />
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
