'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, BookOpen, Zap, Loader2, ImageIcon,
  HelpCircle, Layers, Volume2, Video, ChevronLeft, ChevronRight,
  CheckCircle2, XCircle,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ConceptImage  { id: string; url: string; caption: string; }
interface QuizQuestion  { id: string; question: string; options: string[]; correct_idx: number; explanation: string; }
interface Flashcard     { id: string; front: string; back: string; }

interface ConceptDetail {
  id: string; title: string; description?: string;
  content_text?: string; study_set_id?: string;
  ai_summary?: string; pipeline_status?: string;
  quiz_status?: string; flashcard_status?: string; audio_status?: string;
  has_audio?: boolean; audio_url?: string;
  images: ConceptImage[];
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

  // Quiz state
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({});

  // Flashcard state
  const [cardIndex,   setCardIndex]  = useState(0);
  const [flipped,     setFlipped]    = useState(false);

  const authH = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    loadAll();
  }, [user, conceptId]);

  async function loadAll() {
    setLoading(true);
    try {
      const [conceptRes, assetsRes] = await Promise.all([
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authH }),
        fetch(`${API_BASE}/api/courses/concepts/${conceptId}/assets`, { headers: authH }),
      ]);
      if (conceptRes.ok) setConcept(await conceptRes.json());
      if (assetsRes.ok)  setAssets(await assetsRes.json());
    } finally { setLoading(false); }
  }

  async function startLearning() {
    if (!concept?.study_set_id) return;
    setActivating(true);
    try {
      await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/activate`, {
        method: 'POST', headers: authH,
      });
      router.push(`/study/${concept.study_set_id}`);
    } finally { setActivating(false); }
  }

  function selectAnswer(qi: number, oi: number) {
    setQuizAnswers(prev => prev[qi] !== undefined ? prev : { ...prev, [qi]: oi });
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
          <div className="text-[var(--tx2)] text-sm leading-relaxed whitespace-pre-wrap">{explanation}</div>
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

      {/* Flashcards */}
      {showFlashcards && currentCard && (
        <div className="mb-6">
          <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Layers size={12} /> Flashcards · {cardIndex + 1} of {flashcards.length}
          </h2>

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
                <p className="text-[var(--tx1)] text-base font-semibold">{currentCard.front}</p>
                <p className="text-[var(--tx8)] text-xs mt-3">Tap to reveal</p>
              </div>

              {/* Back */}
              <div className="absolute inset-0 bg-purple-600/10 border border-purple-500/30 rounded-2xl p-8 flex flex-col items-center justify-center text-center"
                style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}>
                <p className="text-[var(--tx1)] text-sm leading-relaxed">{currentCard.back}</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
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
                  <p className="text-[var(--tx1)] text-sm font-medium mb-3">{qi + 1}. {q.question}</p>
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
                          <span className="flex-1">{opt}</span>
                          {answered && oi === q.correct_idx && <CheckCircle2 size={14} className="text-green-400 shrink-0" />}
                          {answered && oi === chosen && oi !== q.correct_idx && <XCircle size={14} className="text-red-400 shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                  {answered && q.explanation && (
                    <div className={`mt-3 text-xs p-3 rounded-xl border ${correct ? 'bg-green-500/10 border-green-500/20 text-green-300' : 'bg-[var(--ov1)] border-[var(--bd)] text-[var(--tx6)]'}`}>
                      💡 {q.explanation}
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

      {/* CTA */}
      <div className={`rounded-2xl border p-5 text-center ${
        concept.study_set_id ? 'bg-[var(--surface)] border-[var(--bd)]' : 'bg-[var(--ov1)] border-dashed border-[var(--bd)]'
      }`}>
        {concept.study_set_id ? (
          <>
            <p className="text-[var(--tx3)] text-sm mb-3">Ready to study with flashcards and videos?</p>
            <button onClick={startLearning} disabled={activating}
              className="inline-flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-500
                         text-white font-medium rounded-xl transition-all disabled:opacity-40">
              {activating ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
              Start learning
            </button>
          </>
        ) : (
          <>
            <p className="text-[var(--tx3)] text-sm font-medium mb-1">Study materials coming soon</p>
            <p className="text-[var(--tx7)] text-xs">Your teacher is preparing materials for this concept</p>
          </>
        )}
      </div>
    </div>
  );
}
