'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';
import { MathText } from '@/components/ui/MathText';
import {
  ArrowLeft, BookOpen, MessageSquare, Loader2, ImageIcon,
  HelpCircle, Layers, Video, ChevronLeft, ChevronRight,
  CheckCircle2, XCircle, Send, FileText, Dumbbell, FlaskConical, Printer,
} from 'lucide-react';
import { ConceptTextbook } from '@/components/course/ConceptTextbook';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ConceptImage  { id: string; url: string; caption: string; }
interface QuizQuestion  { id: string; question: string; options: string[]; correct_idx: number; explanation: string; }
interface Flashcard     { id: string; front: string; back: string; is_due?: boolean; }
interface ConceptResource { id: string; type: 'image' | 'pdf' | 'video'; title: string; file_url?: string; video_url?: string; }

interface ConceptDetail {
  id: string; title: string; description?: string;
  content_text?: string; study_set_id?: string;
  ai_summary?: string; pipeline_status?: string;
  quiz_status?: string; flashcard_status?: string; audio_status?: string;
  has_audio?: boolean; audio_url?: string;
  student_questions?: string[];
  images: ConceptImage[];
  resources: ConceptResource[];
}

interface Assets {
  quiz_status: string; flashcard_status: string; audio_status: string; video_status: string;
  has_audio: boolean; audio_url?: string; video_url?: string;
  quiz: QuizQuestion[]; flashcards: Flashcard[];
}

export default function StudentConceptDetailPage() {
  const router      = useRouter();
  const params      = useParams();
  const classroomId = params.id        as string;
  const courseId    = params.courseId  as string;
  const conceptId   = params.conceptId as string;
  const { user, token } = useSessionStore();
  const { language, t } = useTranslation();

  const [concept,    setConcept]    = useState<ConceptDetail | null>(null);
  const [assets,     setAssets]     = useState<Assets | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [hasBlocks,      setHasBlocks]      = useState(false);
  const [activeTab,      setActiveTab]      = useState<'learn' | 'materials' | 'practice' | 'lab' | 'chat'>('learn');

  // Lab sheet
  interface LabContent { objective: string; materials: string[]; safety: string[]; procedure: string[]; data_table: { title: string; headers: string[]; rows: number }; analysis_questions: string[]; conclusion_prompt: string; }
  const [labContent,  setLabContent2]  = useState<LabContent | null>(null);
  const [labLoaded2,  setLabLoaded2]   = useState(false);

  // Chat Q&A state
  type ChatMsg = { role: 'user' | 'assistant'; content: string };
  const [chatConvId,  setChatConvId]  = useState<string | null>(null);
  const [chatMsgs,    setChatMsgs]    = useState<ChatMsg[]>([]);
  const [chatLoaded,  setChatLoaded]  = useState(false);
  const [chatInput,   setChatInput]   = useState('');
  const [chatSending, setChatSending] = useState(false);
  const [directMode,  setDirectMode]  = useState(false);
  // resource context: when set, next message carries this resource_id for vision/PDF grounding
  const [chatResource, setChatResource] = useState<{ id: string; title: string; type: string } | null>(null);
  const chatEndRef         = useRef<HTMLDivElement>(null);
  const legacyMaxWatchRef  = useRef(0);
  const lastActivityRef    = useRef(Date.now()); // updated on any user interaction

  // Curriculum context (TEKS banner) — null means no context for this course
  const [curriculum, setCurriculum] = useState<{
    driving_question?: string;
    teks_codes?: string[];
    active_lesson?: number;
    lesson_count?: number;
  } | null>(null);

  // Quiz state
  const [quizAnswers, setQuizAnswers]   = useState<Record<number, number>>({});
  const [scoreSubmitted, setScoreSubmitted] = useState(false);

  // Flashcard state — same Again/Got it review pattern as study-set flashcards
  const [cardIndex,    setCardIndex]    = useState(0);
  const [flipped,      setFlipped]      = useState(false);
  const [cardsDone,    setCardsDone]    = useState<Set<number>>(new Set());
  const [cardsAgain,   setCardsAgain]   = useState<number[]>([]);
  const [deckFinished, setDeckFinished] = useState(false);
  const [reviewing,    setReviewing]    = useState(false);

  const authH = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    loadAll();
    // Mark this concept as visited just by opening the unified page —
    // progress no longer requires going through the chat-based "Start learning" flow.
    fetch(`${API_BASE}/api/courses/concepts/${conceptId}/activate`, { method: 'POST', headers: authH }).catch(() => {});
  }, [user, conceptId]);

  async function loadAll() {
    setLoading(true);
    try {
      const [conceptRes, assetsRes, currRes, labRes] = await Promise.all([
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authH }),
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/assets`, { headers: authH }),
        fetch(`${API_BASE}/api/courses/${courseId}/curriculum-context`),
        fetch(`${API_BASE}/api/lab-sheets/${conceptId}`, { headers: authH }),
      ]);
      if (conceptRes.ok) setConcept(await conceptRes.json());
      if (assetsRes.ok)  setAssets(await assetsRes.json());
      if (currRes.ok) {
        const ctx = await currRes.json();
        if (ctx.driving_question) setCurriculum(ctx);
      }
      if (labRes.ok) {
        const lab = await labRes.json();
        if (lab.status === 'published' && lab.content) {
          setLabContent2(lab.content);
          setLabLoaded2(true);
        }
      }
    } finally { setLoading(false); }
  }

  // Track user activity — any interaction resets the idle clock
  useEffect(() => {
    const onActivity = () => { lastActivityRef.current = Date.now(); };
    const onVisibility = () => {
      // Tab hidden → force idle; tab visible again → restart clock
      lastActivityRef.current = document.hidden ? 0 : Date.now();
    };
    const events = ['mousemove', 'keydown', 'scroll', 'click', 'touchstart'] as const;
    events.forEach(e => window.addEventListener(e, onActivity, { passive: true }));
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      events.forEach(e => window.removeEventListener(e, onActivity));
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  // Heartbeat — only fires when student was active in the last 60 s and tab is visible
  useEffect(() => {
    if (!user || !token) return;
    const INTERVAL     = 30_000;
    const IDLE_CUTOFF  = 60_000; // 60 s without any input = idle
    const iv = setInterval(() => {
      if (document.hidden) return;
      if (Date.now() - lastActivityRef.current > IDLE_CUTOFF) return;
      fetch(`${API_BASE}/api/courses/concepts/${conceptId}/heartbeat`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ seconds: INTERVAL / 1000 }),
      }).catch(() => {});
    }, INTERVAL);
    return () => clearInterval(iv);
  }, [user, token, conceptId]);

  const LEGACY_WATCH_THRESHOLDS = [10, 25, 50, 75, 90, 100];

  function handleLegacyVideoTimeUpdate(e: React.SyntheticEvent<HTMLVideoElement>) {
    const vid = e.currentTarget;
    if (!vid.duration || !token) return;
    const pct = Math.floor((vid.currentTime / vid.duration) * 100);
    const next = LEGACY_WATCH_THRESHOLDS.find(t => t > legacyMaxWatchRef.current && pct >= t);
    if (next !== undefined) {
      legacyMaxWatchRef.current = next;
      fetch(`${API_BASE}/api/courses/concepts/${conceptId}/video-progress`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ pct: next }),
      }).catch(() => {});
    }
  }

  function handleLegacyVideoEnded() {
    if (!token || legacyMaxWatchRef.current >= 100) return;
    legacyMaxWatchRef.current = 100;
    fetch(`${API_BASE}/api/courses/concepts/${conceptId}/video-progress`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ pct: 100 }),
    }).catch(() => {});
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMsgs]);

  useEffect(() => {
    if (activeTab === 'lab' && !labLoaded2) {
      fetch(`${API_BASE}/api/lab-sheets/${conceptId}`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.content) setLabContent2(d.content); })
        .finally(() => setLabLoaded2(true));
    }
    if (activeTab === 'chat' && !chatLoaded) {
      setChatLoaded(true);
      fetch(`${API_BASE}/api/courses/concepts/${conceptId}/student-chat`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data?.conversation_id) setChatConvId(data.conversation_id);
          if (data?.messages?.length) {
            setChatMsgs(data.messages.map((m: { role: string; content: string }) => ({
              role: m.role as 'user' | 'assistant',
              content: m.content,
            })));
          }
        })
        .catch(() => {});
    }
  }, [activeTab, labLoaded2, chatLoaded]);

  async function _doSendChat(msg: string, resource: typeof chatResource, isDirect: boolean) {
    setChatMsgs(prev => [...prev, { role: 'user', content: msg }]);
    setChatSending(true);
    try {
      const body: Record<string, unknown> = { message: msg, language, direct: isDirect };
      if (chatConvId) body.conversation_id = chatConvId;
      if (resource)   body.resource_id     = resource.id;
      const res  = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/student-chat`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.conversation_id) setChatConvId(data.conversation_id);
      setChatMsgs(prev => [...prev, { role: 'assistant', content: data.reply ?? 'Sorry, something went wrong.' }]);
    } catch {
      setChatMsgs(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
    } finally { setChatSending(false); }
  }

  async function sendChatMessage(e: React.FormEvent) {
    e.preventDefault();
    const msg = chatInput.trim();
    if (!msg || chatSending) return;
    const resource = chatResource;
    setChatInput('');
    setChatResource(null);
    await _doSendChat(msg, resource, directMode);
  }

  async function sendQuestion(question: string) {
    if (chatSending) return;
    await _doSendChat(question, null, directMode);
  }

  function selectAnswer(qi: number, oi: number) {
    setQuizAnswers(prev => {
      if (prev[qi] !== undefined) return prev;
      const next = { ...prev, [qi]: oi };
      const quiz = assets?.quiz ?? [];
      if (!scoreSubmitted && Object.keys(next).length === quiz.length && quiz.length > 0) {
        const answers = quiz.map((q, i) => ({
          qi:       i,
          question: q.question,
          chosen:   next[i],
          correct:  q.correct_idx,
          ok:       next[i] === q.correct_idx,
        }));
        const correct = answers.filter(a => a.ok).length;
        const score   = (correct / quiz.length) * 100;
        setScoreSubmitted(true);
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/quiz/score`, {
          method: 'POST', headers: authH, body: JSON.stringify({ score, answers }),
        }).catch(() => {});
      }
      return next;
    });
  }

  function nextCard() {
    if (!assets) return;
    setFlipped(false);
    setTimeout(() => setCardIndex(i => Math.min(i + 1, assets.flashcards.length - 1)), 150);
  }
  function prevCard() {
    setFlipped(false);
    setTimeout(() => setCardIndex(i => Math.max(i - 1, 0)), 150);
  }

  async function recordCardReview(rating: 1 | 4) {
    const card = assets?.flashcards[cardIndex];
    if (!card) return;
    setReviewing(true);
    await fetch(`${API_BASE}/api/courses/concepts/flashcards/${card.id}/review`, {
      method: 'POST', headers: authH, body: JSON.stringify({ rating }),
    }).catch(() => {});
    setReviewing(false);
  }
  async function handleCardGotIt() {
    await recordCardReview(4);
    setCardsDone(p => new Set([...p, cardIndex]));
    advanceCard();
  }
  async function handleCardAgain() {
    await recordCardReview(1);
    setCardsAgain(p => [...p, cardIndex]);
    advanceCard();
  }
  function advanceCard() {
    setFlipped(false);
    const total = assets?.flashcards.length ?? 0;
    const n = cardIndex + 1;
    if (n >= total) setDeckFinished(true); else setCardIndex(n);
  }
  function restartDeck() {
    setCardIndex(0); setFlipped(false);
    setCardsDone(new Set()); setCardsAgain([]); setDeckFinished(false);
  }

  function toEmbedUrl(url: string): string | null {
    try {
      const u = new URL(url);
      if (u.hostname.includes('youtube.com') || u.hostname.includes('youtu.be')) {
        const id = u.searchParams.get('v') || u.pathname.split('/').pop() || '';
        return id ? `https://www.youtube.com/embed/${id}` : null;
      }
      if (u.hostname.includes('vimeo.com')) {
        const id = u.pathname.split('/').pop() || '';
        return id ? `https://player.vimeo.com/video/${id}` : null;
      }
      return url;
    } catch { return null; }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!concept) return null;

  const explanation = concept.pipeline_status === 'approved' && concept.ai_summary
    ? concept.ai_summary
    : concept.content_text;

  const showVideo      = assets?.video_status === 'approved' && assets.video_url;
  const showFlashcards = assets?.flashcard_status === 'approved' && (assets.flashcards?.length ?? 0) > 0;
  const showQuiz       = assets?.quiz_status === 'approved' && (assets.quiz?.length ?? 0) > 0;
  const flashcards     = assets?.flashcards ?? [];
  const quiz           = assets?.quiz ?? [];
  const currentCard    = flashcards[cardIndex];

  const hasResources = (concept.resources?.length ?? 0) > 0;
  const hasPractice  = showFlashcards || showQuiz;

  const tabs = [
    { key: 'learn',     label: t.concept.tabLearn,     icon: <BookOpen size={13} /> },
    ...(hasResources ? [{ key: 'materials', label: t.concept.tabMaterials, icon: <FileText size={13} /> }] : []),
    ...(hasPractice  ? [{ key: 'practice',  label: t.concept.tabPractice,  icon: <Dumbbell size={13} /> }] : []),
    ...(labContent ? [{ key: 'lab', label: 'Lab', icon: <FlaskConical size={13} /> }] : []),
    { key: 'chat', label: 'Chat', icon: <MessageSquare size={13} /> },
  ];

  return (
    <div className="p-6 max-w-2xl mx-auto pb-16">

      {/* Back */}
      <button onClick={() => router.push(`/classrooms/${classroomId}/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-4 transition-colors">
        <ArrowLeft size={15} /> {t.concept.backToCourse}
      </button>

      {/* Driving Question Banner — only shown for TEKS-aligned courses */}
      {curriculum?.driving_question && (
        <div className="mb-4 rounded-xl border border-green-500/20 bg-green-500/5 px-4 py-3">
          <div className="flex items-start gap-2.5">
            <span className="text-green-400 text-xs font-semibold uppercase tracking-wider mt-0.5 shrink-0">
              Driving Question
            </span>
            <p className="text-[var(--tx2)] text-sm leading-snug">{curriculum.driving_question}</p>
          </div>
          {curriculum.teks_codes && curriculum.teks_codes.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {curriculum.teks_codes.map(code => (
                <span key={code}
                  className="text-xs px-2 py-0.5 rounded-md bg-green-500/10 text-green-400 border border-green-500/20 font-mono">
                  {code}
                </span>
              ))}
              {curriculum.active_lesson && curriculum.lesson_count && (
                <span className="text-xs px-2 py-0.5 rounded-md bg-[var(--ov2)] text-[var(--tx7)] border border-[var(--bd)]">
                  Lesson {curriculum.active_lesson}/{curriculum.lesson_count}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Title */}
      <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{concept.title}</h1>
      {concept.description && <p className="text-[var(--tx6)] text-sm mb-4">{concept.description}</p>}

      {/* Tab bar */}
      {tabs.length > 1 && (
        <div className="flex gap-1 mb-6 border-b border-[var(--bd)]">
          {tabs.map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                activeTab === tab.key
                  ? 'border-purple-500 text-purple-400'
                  : 'border-transparent text-[var(--tx6)] hover:text-[var(--tx2)]'
              }`}>
              {tab.icon}{tab.label}
            </button>
          ))}
        </div>
      )}

      {/* ── Learn tab ── */}
      {activeTab === 'learn' && (
        <>
          {/* Textbook content blocks */}
          <ConceptTextbook conceptId={conceptId} token={token!} onHasBlocks={setHasBlocks} trackProgress />

          {/* Legacy single-asset view (only when no textbook blocks) */}
          {!hasBlocks && showVideo && (
            <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden mb-6">
              <video controls src={`${API_BASE}${assets!.video_url}`} className="w-full aspect-video"
                onTimeUpdate={handleLegacyVideoTimeUpdate}
                onEnded={handleLegacyVideoEnded}
              />
              <p className="px-4 py-2 text-[var(--tx8)] text-xs flex items-center gap-1.5">
                <Video size={11} /> {t.concept.videoLesson}
              </p>
            </div>
          )}
          {!hasBlocks && explanation && (
            <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-6 mb-6">
              <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <BookOpen size={12} />
                {concept.pipeline_status === 'approved' ? t.concept.summary : t.concept.explanation}
              </h2>
              <div className="text-[var(--tx2)] text-sm leading-relaxed [&>p]:mb-2 [&>p:last-child]:mb-0">
                <MathText>{explanation}</MathText>
              </div>
            </div>
          )}
          {!hasBlocks && concept.images.length > 0 && (
            <div className="mb-6">
              <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <ImageIcon size={12} /> {t.concept.illustrations}
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {concept.images.map(img => (
                  <figure key={img.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                    <img src={`${API_BASE}${img.url}`} alt={img.caption || concept.title}
                      className="w-full aspect-video object-contain bg-[var(--ov2)]" />
                    {img.caption && <figcaption className="px-3 py-2 text-xs text-[var(--tx6)]">{img.caption}</figcaption>}
                  </figure>
                ))}
              </div>
            </div>
          )}

          {/* Prompt to explore other tabs */}
          {(hasResources || hasPractice) && (
            <div className="flex gap-2 flex-wrap mt-2 mb-6">
              {hasResources && (
                <button onClick={() => setActiveTab('materials')}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[var(--bd)]
                             text-[var(--tx6)] hover:text-[var(--tx2)] hover:border-purple-500/40 transition-colors">
                  <FileText size={11} /> {t.concept.viewMaterials}
                </button>
              )}
              {hasPractice && (
                <button onClick={() => setActiveTab('practice')}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[var(--bd)]
                             text-[var(--tx6)] hover:text-[var(--tx2)] hover:border-purple-500/40 transition-colors">
                  <Dumbbell size={11} /> {t.concept.practicePrompt}
                </button>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Materials tab ── */}
      {activeTab === 'materials' && hasResources && (
        <div className="space-y-4">
          {/* Resource images */}
          {concept.resources.filter(r => r.type === 'image').length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              {concept.resources.filter(r => r.type === 'image').map(r => (
                <figure key={r.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                  <img src={`${API_BASE}${r.file_url}`} alt={r.title}
                    className="w-full aspect-video object-contain bg-[var(--ov2)]" />
                  {r.title && (
                    <div className="px-3 py-2">
                      <figcaption className="text-xs text-[var(--tx6)] truncate">{r.title}</figcaption>
                    </div>
                  )}
                </figure>
              ))}
            </div>
          )}

          {/* PDFs */}
          {concept.resources.filter(r => r.type === 'pdf').map(r => (
            <div key={r.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3">
                <FileText size={18} className="text-purple-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--tx1)] truncate">{r.title}</p>
                  <p className="text-xs text-[var(--tx7)]">{t.concept.pdfDocument}</p>
                </div>
                <a href={`${API_BASE}${r.file_url}`} target="_blank" rel="noreferrer"
                  className="text-xs text-purple-400 hover:text-purple-300 transition-colors shrink-0">
                  {t.studySets.openPdf}
                </a>
              </div>
            </div>
          ))}

          {/* Videos */}
          {concept.resources.filter(r => r.type === 'video').map(r => {
            const embedUrl = r.video_url ? toEmbedUrl(r.video_url) : null;
            return (
              <div key={r.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                {embedUrl ? (
                  <div className="aspect-video">
                    <iframe src={embedUrl} title={r.title}
                      allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
                      allowFullScreen className="w-full h-full" />
                  </div>
                ) : (
                  <div className="flex items-center gap-3 px-4 py-3">
                    <Video size={18} className="text-purple-400 shrink-0" />
                    <a href={r.video_url} target="_blank" rel="noreferrer"
                      className="text-sm text-purple-400 hover:text-purple-300 transition-colors truncate">{r.title}</a>
                  </div>
                )}
                {r.title && <p className="px-4 py-2 text-xs text-[var(--tx6)] border-t border-[var(--bd)]">{r.title}</p>}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Practice tab ── */}
      {activeTab === 'practice' && hasPractice && (
        <div className="space-y-8">
          {/* Flashcards */}
          {showFlashcards && (
            <div>
              <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <Layers size={12} /> {t.concept.tabPractice} · {Math.min(cardIndex + 1, flashcards.length)} / {flashcards.length}
                {flashcards.filter(c => c.is_due).length > 0 && ` · ${flashcards.filter(c => c.is_due).length} ${t.classrooms.flashcardsDue}`}
              </h2>

              {deckFinished ? (
                <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 flex flex-col items-center text-center gap-3">
                  <CheckCircle2 size={28} className="text-green-400" />
                  <p className="text-[var(--tx1)] font-semibold">{t.concept.deckComplete}</p>
                  <p className="text-[var(--tx7)] text-sm">{cardsDone.size} {t.concept.gotIt} · {cardsAgain.length} {t.concept.again}</p>
                  <button onClick={restartDeck}
                    className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all">
                    {t.studySets.studyAgain}
                  </button>
                </div>
              ) : currentCard && (
                <>
                  <div onClick={() => setFlipped(f => !f)} className="relative cursor-pointer select-none" style={{ perspective: '1000px' }}>
                    <div className="relative w-full transition-transform duration-300"
                      style={{ transformStyle: 'preserve-3d', transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)' }}>
                      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 min-h-[140px] flex flex-col items-center justify-center text-center"
                        style={{ backfaceVisibility: 'hidden' }}>
                        <p className="text-[var(--tx1)] text-base font-semibold"><MathText inline>{currentCard.front}</MathText></p>
                        <p className="text-[var(--tx8)] text-xs mt-3">{t.concept.tapToReveal}</p>
                      </div>
                      <div className="absolute inset-0 bg-purple-600/10 border border-purple-500/30 rounded-2xl p-8 flex flex-col items-center justify-center text-center"
                        style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}>
                        <p className="text-[var(--tx1)] text-sm leading-relaxed"><MathText inline>{currentCard.back}</MathText></p>
                      </div>
                    </div>
                  </div>

                  {flipped ? (
                    <div className="flex gap-3 mt-3">
                      <button onClick={handleCardAgain} disabled={reviewing}
                        className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 text-amber-400 text-sm font-medium transition-colors disabled:opacity-50">
                        {t.concept.again}
                      </button>
                      <button onClick={handleCardGotIt} disabled={reviewing}
                        className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-green-500/10 hover:bg-green-500/20 border border-green-500/20 text-green-400 text-sm font-medium transition-colors disabled:opacity-50">
                        <CheckCircle2 size={14} /> {t.concept.gotIt}
                      </button>
                    </div>
                  ) : (
                    <button onClick={() => setFlipped(true)}
                      className="w-full mt-3 px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all">
                      {t.concept.revealAnswer}
                    </button>
                  )}

                  <div className="flex items-center justify-center gap-4 mt-3">
                    <button onClick={prevCard} disabled={cardIndex === 0}
                      className="p-2 rounded-xl bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] disabled:opacity-30 transition-all">
                      <ChevronLeft size={18} />
                    </button>
                    <div className="flex gap-1">
                      {flashcards.map((_, i) => (
                        <button key={i} onClick={() => { setFlipped(false); setCardIndex(i); }}
                          className={`w-1.5 h-1.5 rounded-full transition-all ${i === cardIndex ? 'bg-purple-400 w-4' : 'bg-[var(--tx8)]'}`} />
                      ))}
                    </div>
                    <button onClick={nextCard} disabled={cardIndex === flashcards.length - 1}
                      className="p-2 rounded-xl bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] disabled:opacity-30 transition-all">
                      <ChevronRight size={18} />
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Quiz */}
          {showQuiz && (
            <div>
              <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
                <HelpCircle size={12} /> Quiz · {t.quiz.questionsCount.replace('{n}', String(quiz.length))}
              </h2>
              <div className="space-y-4">
                {quiz.map((q, qi) => {
                  const chosen   = quizAnswers[qi];
                  const answered = chosen !== undefined;
                  const correct  = chosen === q.correct_idx;
                  return (
                    <div key={q.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4">
                      <p className="text-[var(--tx1)] text-sm font-medium mb-3">{qi + 1}. <MathText inline>{q.question}</MathText></p>
                      <div className="space-y-2">
                        {q.options.map((opt, oi) => {
                          let cls = 'bg-[var(--ov1)] border-[var(--bd)] text-[var(--tx2)] hover:border-purple-500/50 hover:bg-[var(--ov2)]';
                          if (answered) {
                            if (oi === q.correct_idx) cls = 'bg-green-500/15 border-green-500/40 text-green-400';
                            else if (oi === chosen)   cls = 'bg-red-500/15 border-red-500/40 text-red-400';
                            else                      cls = 'bg-[var(--ov1)] border-[var(--bd)] text-[var(--tx7)] opacity-60';
                          }
                          return (
                            <button key={oi} onClick={() => selectAnswer(qi, oi)} disabled={answered}
                              className={`w-full text-left flex items-center gap-3 px-4 py-3 border rounded-xl text-sm transition-all ${cls}`}>
                              <span className="font-mono text-xs opacity-70">{String.fromCharCode(65 + oi)}</span>
                              <span className="flex-1"><MathText inline>{opt}</MathText></span>
                              {answered && oi === q.correct_idx && <CheckCircle2 size={14} className="text-green-400 shrink-0" />}
                              {answered && oi === chosen && oi !== q.correct_idx && <XCircle size={14} className="text-red-400 shrink-0" />}
                            </button>
                          );
                        })}
                      </div>
                      {answered && q.explanation && (
                        <div className={`mt-3 text-xs p-3 rounded-xl border ${correct ? 'bg-green-500/10 border-green-500/20 text-green-300' : 'bg-[var(--ov1)] border-[var(--bd)] text-[var(--tx6)]'}`}>
                          <span>💡 </span><MathText inline>{q.explanation}</MathText>
                        </div>
                      )}
                    </div>
                  );
                })}
                {Object.keys(quizAnswers).length === quiz.length && quiz.length > 0 && (
                  <div className="bg-purple-500/10 border border-purple-500/20 rounded-2xl p-4 text-center">
                    <p className="text-purple-300 font-semibold text-lg">
                      {Object.entries(quizAnswers).filter(([qi, oi]) => oi === quiz[Number(qi)].correct_idx).length}/{quiz.length} {t.quiz.correct}
                    </p>
                    <p className="text-[var(--tx7)] text-xs mt-1">
                      {Object.entries(quizAnswers).filter(([qi, oi]) => oi === quiz[Number(qi)].correct_idx).length === quiz.length
                        ? t.concept.perfectScore : t.concept.reviewExplanations}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Lab Sheet tab content ── */}
      {activeTab === 'lab' && (
        <div className="mb-6">
          {!labLoaded2 ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={20} className="text-purple-400 animate-spin" />
            </div>
          ) : !labContent ? (
            <div className="text-center py-12 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl">
              <FlaskConical size={28} className="text-[var(--tx8)] mx-auto mb-2" />
              <p className="text-[var(--tx6)] text-sm">No lab sheet available yet.</p>
              <p className="text-[var(--tx8)] text-xs mt-1">Your teacher will publish one when it's ready.</p>
            </div>
          ) : (
            <div className="space-y-4 print:space-y-3">
              {/* Print button */}
              <div className="flex justify-end print:hidden">
                <button onClick={() => window.print()}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[var(--bd)] rounded-xl text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all">
                  <Printer size={12} /> Print lab sheet
                </button>
              </div>

              {/* Objective */}
              <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4">
                <p className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-1">Objective</p>
                <p className="text-[var(--tx2)] text-sm">{labContent.objective}</p>
              </div>

              {/* Materials + Safety */}
              <div className="grid grid-cols-2 gap-3">
                {([['materials','Materials'],['safety','Safety']] as const).map(([field, label]) => (
                  <div key={field} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4">
                    <p className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-1">{label}</p>
                    <ul className="space-y-0.5">
                      {labContent[field].map((item, i) => (
                        <li key={i} className="text-[var(--tx2)] text-xs flex items-start gap-1.5">
                          <span className="text-[var(--tx7)] shrink-0 mt-0.5">•</span>{item}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              {/* Procedure */}
              <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4">
                <p className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-2">Procedure</p>
                <ol className="space-y-2">
                  {labContent.procedure.map((step, i) => (
                    <li key={i} className="flex items-start gap-2.5">
                      <span className="text-purple-400 font-bold text-xs shrink-0 w-5 text-right mt-0.5">{i + 1}.</span>
                      <p className="text-[var(--tx2)] text-sm">{step}</p>
                    </li>
                  ))}
                </ol>
              </div>

              {/* Data Table */}
              {labContent.data_table.headers.length > 0 && (
                <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4">
                  <p className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-2">
                    {labContent.data_table.title || 'Data Table'}
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse">
                      <thead>
                        <tr>
                          {labContent.data_table.headers.map((h, i) => (
                            <th key={i} className="border border-[var(--bd)] px-3 py-2 text-left text-[var(--tx3)] font-semibold bg-[var(--ov1)]">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Array.from({ length: labContent.data_table.rows }).map((_, r) => (
                          <tr key={r}>
                            {labContent.data_table.headers.map((_, c) => (
                              <td key={c} className="border border-[var(--bd)] px-3 py-4 text-[var(--tx8)]" />
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Analysis Questions */}
              <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4">
                <p className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-2">Analysis Questions</p>
                <ol className="space-y-4">
                  {labContent.analysis_questions.map((q, i) => (
                    <li key={i} className="flex items-start gap-2.5">
                      <span className="text-purple-400 font-bold text-xs shrink-0 w-5 text-right mt-0.5">{i + 1}.</span>
                      <div className="flex-1">
                        <p className="text-[var(--tx2)] text-sm mb-2">{q}</p>
                        <div className="border-b border-[var(--bd)] mt-6" />
                        <div className="border-b border-[var(--bd)] mt-6" />
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              {/* Conclusion */}
              <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4">
                <p className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-1">Conclusion</p>
                <p className="text-[var(--tx2)] text-sm mb-4">{labContent.conclusion_prompt}</p>
                <div className="border-b border-[var(--bd)] mt-6" />
                <div className="border-b border-[var(--bd)] mt-6" />
                <div className="border-b border-[var(--bd)] mt-6" />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Chat tab content ── */}
      {activeTab === 'chat' && (
        <div className="rounded-2xl border bg-[var(--surface)] border-[var(--bd)] overflow-hidden mt-6">
          <div className="px-4 py-3 space-y-3 max-h-[480px] overflow-y-auto">
            {chatMsgs.length === 0 && (
              <p className="text-[var(--tx7)] text-sm text-center py-4">
                {t.concept.chatAskAnything} <span className="text-[var(--tx3)] font-medium">{concept.title}</span>
              </p>
            )}
            {chatMsgs.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'user' ? (
                  <div className="max-w-[80%] bg-purple-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[85%] bg-[var(--ov1)] border border-[var(--bd)] rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm text-[var(--tx2)] prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}>
                      {preprocessMath(msg.content)}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            ))}
            {chatSending && (
              <div className="flex justify-start">
                <div className="bg-[var(--ov1)] border border-[var(--bd)] rounded-2xl rounded-tl-sm px-4 py-2.5">
                  <Loader2 size={14} className="animate-spin text-purple-400" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {chatResource && (
            <div className="flex items-center gap-2 px-4 py-2 border-t border-[var(--bd)] bg-purple-500/5">
              <span className="text-xs text-purple-400">
                {chatResource.type === 'image' ? '🖼' : '📄'} Asking about: <span className="font-medium">{chatResource.title}</span>
              </span>
              <button onClick={() => setChatResource(null)} className="ml-auto text-[var(--tx8)] hover:text-[var(--tx3)] text-xs">✕</button>
            </div>
          )}

          {concept.student_questions && concept.student_questions.length > 0 && (
            <div className="px-4 pt-2 pb-1 flex flex-wrap gap-1.5 border-t border-[var(--bd)]">
              {concept.student_questions.map((q, i) => (
                <button key={i} onClick={() => sendQuestion(q)} disabled={chatSending}
                  className="text-xs px-2.5 py-1 rounded-full border border-purple-500/30 bg-purple-500/8
                             text-purple-300 hover:bg-purple-500/20 hover:border-purple-500/50
                             transition-all disabled:opacity-40 text-left">
                  {q}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 px-4 py-2 border-t border-[var(--bd)]">
            <button onClick={() => setDirectMode(false)}
              className={`text-xs px-3 py-1 rounded-full border transition-all ${
                !directMode
                  ? 'border-purple-500/50 bg-purple-500/15 text-purple-300'
                  : 'border-[var(--bd)] text-[var(--tx8)] hover:text-[var(--tx5)]'
              }`}>
              Guided
            </button>
            <button onClick={() => setDirectMode(true)}
              className={`text-xs px-3 py-1 rounded-full border transition-all ${
                directMode
                  ? 'border-amber-500/50 bg-amber-500/15 text-amber-300'
                  : 'border-[var(--bd)] text-[var(--tx8)] hover:text-[var(--tx5)]'
              }`}>
              Just tell me
            </button>
            {directMode && (
              <span className="text-[10px] text-amber-400/60 ml-1">direct answers on</span>
            )}
          </div>

          <form onSubmit={sendChatMessage} className="flex gap-2 px-4 py-3 border-t border-[var(--bd)]">
            <input value={chatInput} onChange={e => setChatInput(e.target.value)}
              placeholder={chatResource ? `${t.concept.chatAskAnything} ${chatResource.title}…` : t.concept.chatPlaceholder}
              disabled={chatSending}
              className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                         text-[var(--tx1)] placeholder-[var(--tx8)] focus:outline-none focus:border-purple-500 disabled:opacity-50" />
            <button type="submit" disabled={chatSending || !chatInput.trim()}
              className="p-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
              <Send size={15} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
