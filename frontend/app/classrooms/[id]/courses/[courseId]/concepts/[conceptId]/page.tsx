'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { preprocessMath } from '@/lib/preprocessMath';
import { MathText } from '@/components/ui/MathText';
import {
  ArrowLeft, BookOpen, MessageSquare, Loader2, ImageIcon,
  HelpCircle, Layers, Volume2, Video, ChevronLeft, ChevronRight,
  CheckCircle2, XCircle, Send, FileText,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

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

  const [concept,    setConcept]    = useState<ConceptDetail | null>(null);
  const [assets,     setAssets]     = useState<Assets | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [activating, setActivating] = useState(false);

  // Chat Q&A state
  type ChatMsg = { role: 'user' | 'assistant'; content: string };
  const [chatOpen,    setChatOpen]    = useState(false);
  const [chatConvId,  setChatConvId]  = useState<string | null>(null);
  const [chatMsgs,    setChatMsgs]    = useState<ChatMsg[]>([]);
  const [chatInput,   setChatInput]   = useState('');
  const [chatSending, setChatSending] = useState(false);
  // resource context: when set, next message carries this resource_id for vision/PDF grounding
  const [chatResource, setChatResource] = useState<{ id: string; title: string; type: string } | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

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
      const [conceptRes, assetsRes] = await Promise.all([
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authH }),
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/assets`, { headers: authH }),
      ]);
      if (conceptRes.ok)  setConcept(await conceptRes.json());
      if (assetsRes.ok)   setAssets(await assetsRes.json());
    } finally { setLoading(false); }
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMsgs]);

  async function openChat(resource?: { id: string; title: string; type: string }) {
    if (chatOpen && !resource) { setChatOpen(false); return; }
    if (resource) {
      setChatResource(resource);
      if (!chatOpen) {
        // pre-fill question for the resource
        setChatInput(
          resource.type === 'image'
            ? `Can you explain what this diagram "${resource.title}" shows?`
            : `Can you explain the content from "${resource.title}"?`
        );
      }
    }
    setChatOpen(true);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  }

  async function sendChatMessage(e: React.FormEvent) {
    e.preventDefault();
    const msg = chatInput.trim();
    if (!msg || chatSending) return;
    const resource = chatResource;
    setChatInput('');
    setChatResource(null);
    setChatMsgs(prev => [...prev, { role: 'user', content: msg }]);
    setChatSending(true);
    try {
      const body: Record<string, string> = { message: msg };
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

  function selectAnswer(qi: number, oi: number) {
    setQuizAnswers(prev => {
      if (prev[qi] !== undefined) return prev;
      const next = { ...prev, [qi]: oi };
      const quiz = assets?.quiz ?? [];
      if (!scoreSubmitted && Object.keys(next).length === quiz.length && quiz.length > 0) {
        const correct = Object.entries(next).filter(([i, o]) => o === quiz[Number(i)].correct_idx).length;
        const score   = (correct / quiz.length) * 100;
        setScoreSubmitted(true);
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/quiz/score`, {
          method: 'POST', headers: authH, body: JSON.stringify({ score }),
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
  const showAudio      = !showVideo && assets?.audio_status === 'approved' && assets.has_audio && assets.audio_url;
  const showFlashcards = assets?.flashcard_status === 'approved' && (assets.flashcards?.length ?? 0) > 0;
  const showQuiz       = assets?.quiz_status === 'approved' && (assets.quiz?.length ?? 0) > 0;
  const flashcards     = assets?.flashcards ?? [];
  const quiz           = assets?.quiz ?? [];
  const currentCard    = flashcards[cardIndex];

  return (
    <div className="p-6 max-w-2xl mx-auto pb-16">

      {/* Back */}
      <button onClick={() => router.push(`/classrooms/${classroomId}/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> Back to course
      </button>

      {/* Title */}
      <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{concept.title}</h1>
      {concept.description && <p className="text-[var(--tx6)] text-sm mb-6">{concept.description}</p>}

      {/* Video player (preferred over audio-only) */}
      {showVideo && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden mb-6">
          <video controls src={`${API_BASE}${assets!.video_url}`} className="w-full aspect-video" />
          <p className="px-4 py-2 text-[var(--tx8)] text-xs flex items-center gap-1.5">
            <Video size={11} /> Video lesson
          </p>
        </div>
      )}

      {/* Audio-only fallback when no video */}
      {showAudio && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4 mb-6">
          <p className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Volume2 size={12} /> Listen
          </p>
          <audio controls src={`${API_BASE}${assets!.audio_url}`} className="w-full" />
        </div>
      )}

      {/* Explanation */}
      {explanation && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-6 mb-6">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <BookOpen size={12} />
            {concept.pipeline_status === 'approved' ? 'Summary' : 'Explanation'}
          </h2>
          <div className="text-[var(--tx2)] text-sm leading-relaxed [&>p]:mb-2 [&>p:last-child]:mb-0"><MathText>{explanation}</MathText></div>
        </div>
      )}

      {/* Images */}
      {concept.images.length > 0 && (
        <div className="mb-6">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <ImageIcon size={12} /> Illustrations
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {concept.images.map(img => (
              <figure key={img.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                <img src={`${API_BASE}${img.url}`} alt={img.caption || concept.title}
                  className="w-full aspect-video object-contain bg-[var(--ov2)]" />
                {img.caption && (
                  <figcaption className="px-3 py-2 text-xs text-[var(--tx6)]">{img.caption}</figcaption>
                )}
              </figure>
            ))}
          </div>
        </div>
      )}

      {/* Resources (teacher-uploaded images, PDFs, videos) */}
      {concept.resources?.length > 0 && (
        <div className="mb-6 space-y-3">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5">
            <FileText size={12} /> Learning Materials
          </h2>

          {/* Resource images */}
          {concept.resources.filter(r => r.type === 'image').length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              {concept.resources.filter(r => r.type === 'image').map(r => (
                <figure key={r.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                  <img src={`${API_BASE}${r.file_url}`} alt={r.title}
                    className="w-full aspect-video object-contain bg-[var(--ov2)]" />
                  <div className="px-3 py-2 flex items-center justify-between">
                    {r.title && <figcaption className="text-xs text-[var(--tx6)] truncate">{r.title}</figcaption>}
                    <button onClick={() => openChat({ id: r.id, title: r.title, type: 'image' })}
                      className="text-xs text-purple-400 hover:text-purple-300 transition-colors shrink-0 ml-2">
                      Ask AI →
                    </button>
                  </div>
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
                  <p className="text-xs text-[var(--tx7)]">PDF document</p>
                </div>
                <a href={`${API_BASE}${r.file_url}`} target="_blank" rel="noreferrer"
                  className="text-xs text-purple-400 hover:text-purple-300 transition-colors shrink-0">
                  Open PDF
                </a>
              </div>
              <div className="px-4 pb-3">
                <button
                  onClick={() => openChat({ id: r.id, title: r.title, type: r.type })}
                  className="text-xs text-purple-400 hover:text-purple-300 transition-colors">
                  Ask AI about this →
                </button>
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
                    <iframe src={embedUrl} title={r.title} allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
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

      {/* Flashcards */}
      {showFlashcards && (
        <div className="mb-6">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Layers size={12} /> Flashcards · {Math.min(cardIndex + 1, flashcards.length)} of {flashcards.length}
            {flashcards.filter(c => c.is_due).length > 0 && ` · ${flashcards.filter(c => c.is_due).length} due for review`}
          </h2>

          {deckFinished ? (
            <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 flex flex-col items-center text-center gap-3">
              <CheckCircle2 size={28} className="text-green-400" />
              <p className="text-[var(--tx1)] font-semibold">Deck complete</p>
              <p className="text-[var(--tx7)] text-sm">{cardsDone.size} got it · {cardsAgain.length} to review again</p>
              <button onClick={restartDeck}
                className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all">
                Study again
              </button>
            </div>
          ) : currentCard && (
            <>
              {/* Card */}
              <div
                onClick={() => setFlipped(f => !f)}
                className="relative cursor-pointer select-none"
                style={{ perspective: '1000px' }}
              >
                <div className={`relative w-full transition-transform duration-300`}
                  style={{ transformStyle: 'preserve-3d', transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)' }}>

                  {/* Front */}
                  <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 min-h-[140px] flex flex-col items-center justify-center text-center"
                    style={{ backfaceVisibility: 'hidden' }}>
                    <p className="text-[var(--tx1)] text-base font-semibold"><MathText inline>{currentCard.front}</MathText></p>
                    <p className="text-[var(--tx8)] text-xs mt-3">Tap to reveal</p>
                  </div>

                  {/* Back */}
                  <div className="absolute inset-0 bg-purple-600/10 border border-purple-500/30 rounded-2xl p-8 flex flex-col items-center justify-center text-center"
                    style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}>
                    <p className="text-[var(--tx1)] text-sm leading-relaxed"><MathText inline>{currentCard.back}</MathText></p>
                  </div>
                </div>
              </div>

              {/* Again / Got it */}
              {flipped ? (
                <div className="flex gap-3 mt-3">
                  <button onClick={handleCardAgain} disabled={reviewing}
                    className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl
                               bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20
                               text-amber-400 text-sm font-medium transition-colors disabled:opacity-50">
                    Again
                  </button>
                  <button onClick={handleCardGotIt} disabled={reviewing}
                    className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl
                               bg-green-500/10 hover:bg-green-500/20 border border-green-500/20
                               text-green-400 text-sm font-medium transition-colors disabled:opacity-50">
                    <CheckCircle2 size={14} /> Got it
                  </button>
                </div>
              ) : (
                <button onClick={() => setFlipped(true)}
                  className="w-full mt-3 px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all">
                  Reveal answer
                </button>
              )}

              {/* Manual navigation */}
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
        <div className="mb-6">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <HelpCircle size={12} /> Quiz · {quiz.length} questions
          </h2>
          <div className="space-y-4">
            {quiz.map((q, qi) => {
              const chosen = quizAnswers[qi];
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
                        else                       cls = 'bg-[var(--ov1)] border-[var(--bd)] text-[var(--tx7)] opacity-60';
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

            {/* Score */}
            {Object.keys(quizAnswers).length === quiz.length && (
              <div className="bg-purple-500/10 border border-purple-500/20 rounded-2xl p-4 text-center">
                <p className="text-purple-300 font-semibold text-lg">
                  {Object.entries(quizAnswers).filter(([qi, oi]) => oi === quiz[Number(qi)].correct_idx).length}
                  /{quiz.length} correct
                </p>
                <p className="text-[var(--tx7)] text-xs mt-1">
                  {Object.entries(quizAnswers).filter(([qi, oi]) => oi === quiz[Number(qi)].correct_idx).length === quiz.length
                    ? 'Perfect score! 🎉' : 'Review the explanations above and try again soon'}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chat Q&A */}
      <div className="rounded-2xl border bg-[var(--surface)] border-[var(--bd)] overflow-hidden">
        <button
          onClick={() => openChat()}
          disabled={activating}
          className="w-full flex items-center justify-between px-5 py-4 hover:bg-[var(--ov1)] transition-colors disabled:opacity-50"
        >
          <span className="flex items-center gap-2 text-[var(--tx1)] font-semibold text-sm">
            {activating
              ? <Loader2 size={16} className="animate-spin text-purple-400" />
              : <MessageSquare size={16} className="text-purple-400" />}
            Ask AI about this concept
          </span>
          <span className="text-[var(--tx7)] text-xs">{chatOpen ? 'Close' : 'Open'}</span>
        </button>

        {chatOpen && (
          <div className="border-t border-[var(--bd)]">
            {/* Message list */}
            <div className="px-4 py-3 space-y-3 max-h-80 overflow-y-auto">
              {chatMsgs.length === 0 && (
                <p className="text-[var(--tx7)] text-sm text-center py-4">
                  Ask anything about <span className="text-[var(--tx3)] font-medium">{concept.title}</span>
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
                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
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

            {/* Resource context badge */}
            {chatResource && (
              <div className="flex items-center gap-2 px-4 py-2 border-t border-[var(--bd)] bg-purple-500/5">
                <span className="text-xs text-purple-400">
                  {chatResource.type === 'image' ? '🖼' : '📄'} Asking about: <span className="font-medium">{chatResource.title}</span>
                </span>
                <button onClick={() => setChatResource(null)} className="ml-auto text-[var(--tx8)] hover:text-[var(--tx3)] text-xs">✕</button>
              </div>
            )}

            {/* Input */}
            <form onSubmit={sendChatMessage}
              className="flex gap-2 px-4 py-3 border-t border-[var(--bd)]">
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                placeholder={chatResource ? `Ask about ${chatResource.title}…` : 'Ask a question…'}
                disabled={chatSending}
                className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] placeholder-[var(--tx8)] focus:outline-none focus:border-purple-500
                           disabled:opacity-50"
              />
              <button type="submit" disabled={chatSending || !chatInput.trim()}
                className="p-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl transition-colors
                           disabled:opacity-40 disabled:cursor-not-allowed">
                <Send size={15} />
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
