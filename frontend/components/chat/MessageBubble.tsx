'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Copy, Check, CheckCircle, Loader, Play, XCircle, X, FileText } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { SubjectBadge } from './SubjectBadge';
import { MakeVisualButton } from './MakeVisualButton';
import { preprocessMath } from '@/lib/preprocessMath';
import { getQuiz, getVideoStatus } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    chips?: string[];
    subject?: { subject: string; subtopic: string; icon: string };
    imageUrl?: string;
    quiz_id?: string;
    quiz_topic?: string;
    num_questions?: number;
  };
}

/* ── Quiz card ──────────────────────────────────────────────────────────────── */
function QuizCard({ quizId, topic, numQuestions }: { quizId: string; topic: string; numQuestions?: number }) {
  const router = useRouter();
  const [quizStatus, setQuizStatus] = useState<{
    completed: boolean;
    score?: number | null;
    max_score?: number | null;
  } | null>(null);

  useEffect(() => {
    getQuiz(quizId)
      .then(d => setQuizStatus({ completed: d.completed, score: d.score, max_score: d.max_score }))
      .catch(() => setQuizStatus({ completed: false }));
  }, [quizId]);

  const pct =
    quizStatus?.score != null && quizStatus?.max_score
      ? Math.round((quizStatus.score / quizStatus.max_score) * 100)
      : null;

  return (
    <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-4 py-3.5 space-y-3">
      <div className="flex items-start gap-3">
        <span className="text-xl mt-0.5">📝</span>
        <div>
          <p className="text-[var(--tx2)] text-sm font-semibold leading-snug">{topic}</p>
          {numQuestions != null && (
            <p className="text-[var(--tx6)] text-xs mt-0.5">{numQuestions} questions</p>
          )}
        </div>
      </div>
      {quizStatus === null ? (
        <div className="w-4 h-4 border-2 border-[var(--indigo)] border-t-transparent rounded-full animate-spin ml-8 opacity-50" />
      ) : quizStatus.completed && pct !== null ? (
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--tx3)]">
            ✅ Score:{' '}
            <span className="text-[var(--tx1)] font-semibold">
              {quizStatus.score} / {quizStatus.max_score}
            </span>
            <span className="text-[var(--tx6)] ml-1.5">({pct}%)</span>
          </span>
          <button
            onClick={() => router.push(`/quiz/${quizId}`)}
            className="text-xs px-3 py-1.5 rounded-lg bg-[var(--ov2)] hover:bg-[var(--ov4)]
                       text-[var(--tx3)] hover:text-[var(--tx1)]
                       border border-[var(--bd)] transition-all"
          >
            Review →
          </button>
        </div>
      ) : (
        <button
          onClick={() => router.push(`/quiz/${quizId}`)}
          className="text-sm px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium
                     transition-all flex items-center gap-2 w-fit"
        >
          Start Quiz <span aria-hidden>→</span>
        </button>
      )}
    </div>
  );
}

/* ── Transcript modal ───────────────────────────────────────────────────────── */
type TranscriptTab = 'transcript' | 'solution';

function TranscriptModal({
  transcript,
  solution,
  onClose,
}: {
  transcript: string;
  solution?: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<TranscriptTab>('transcript');

  // Close on Escape key
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const content = tab === 'transcript' ? transcript : (solution ?? '');

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl
                      w-full max-w-2xl max-h-[85vh] flex flex-col
                      shadow-2xl shadow-black/40">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)] shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-purple-600/20 flex items-center justify-center">
              <FileText size={13} className="text-[var(--purple)]" />
            </div>
            <h2 className="text-[var(--tx1)] font-semibold text-sm">Video Content</h2>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                       transition-colors"
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </div>

        {/* Tabs — only show if we have both */}
        {solution && (
          <div className="flex gap-0.5 px-5 pt-3 shrink-0">
            {(['transcript', 'solution'] as TranscriptTab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  tab === t
                    ? 'bg-purple-600/20 text-[var(--purple)]'
                    : 'text-[var(--tx6)] hover:text-[var(--tx2)] hover:bg-[var(--ov2)]'
                }`}
              >
                {t === 'transcript' ? '📖 Transcript' : '🧮 Step-by-step Solution'}
              </button>
            ))}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto no-scrollbar px-6 py-4">
          <div className="ai-content text-sm leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {preprocessMath(content)}
            </ReactMarkdown>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-[var(--bd)] shrink-0 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs rounded-lg bg-[var(--ov3)] hover:bg-[var(--ov4)]
                       text-[var(--tx2)] transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Video status card ──────────────────────────────────────────────────────── */
const VIDEO_STEPS = [
  'Writing solution & script',
  'Planning animation',
  'Generating Manim code',
  'Rendering video',
];

function VideoStatusCard({ videoId, token }: { videoId: number; token?: string }) {
  const router = useRouter();
  const [status,     setStatus]     = useState<string>('pending');
  const [videoUrl,   setVideoUrl]   = useState<string | null>(null);
  const [stepIdx,    setStepIdx]    = useState(0);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [solution,   setSolution]   = useState<string | null>(null);
  const [showModal,  setShowModal]  = useState(false);

  const closeModal = useCallback(() => setShowModal(false), []);

  useEffect(() => {
    let stopped = false;

    async function poll() {
      try {
        const data = await getVideoStatus(videoId, token);
        if (stopped) return;
        setStatus(data.status);
        // Capture transcript / solution whenever they arrive (could come before video is done)
        if (data.transcript_markdown) setTranscript(data.transcript_markdown);
        if (data.verified_solution)   setSolution(data.verified_solution);

        if (data.status === 'complete' || data.status === 'completed') {
          setVideoUrl(data.video_url ?? null);
          return; // stop polling
        }
        if (data.status === 'failed') return; // stop polling
        setStepIdx(prev => (prev + 1) % VIDEO_STEPS.length);
        setTimeout(poll, 4000);
      } catch {
        if (!stopped) setTimeout(poll, 8000); // back-off on error
      }
    }

    poll();
    return () => { stopped = true; };
  }, [videoId]);

  const isDone   = status === 'complete' || status === 'completed';
  const isFailed = status === 'failed';

  /* Shared transcript button — shown whenever transcript is available */
  const transcriptBtn = transcript && (
    <button
      onClick={() => setShowModal(true)}
      className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg
                 bg-[var(--ov2)] hover:bg-[var(--ov4)]
                 text-[var(--tx4)] hover:text-[var(--tx1)]
                 border border-[var(--bd)] transition-all"
    >
      <FileText size={11} />
      Transcript
    </button>
  );

  /* Done */
  if (isDone) {
    return (
      <>
        <div className="rounded-xl border border-purple-500/25 bg-purple-500/5 px-4 py-3.5 space-y-2.5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-purple-600/20 flex items-center justify-center shrink-0">
                <Play size={14} className="text-[var(--purple)] ml-0.5" />
              </div>
              <div>
                <p className="text-[var(--tx2)] text-sm font-semibold">Video ready!</p>
                <p className="text-[var(--tx7)] text-[10px]">Your animation has been generated</p>
              </div>
            </div>
            <button
              onClick={() => router.push(`/videos?id=${videoId}`)}
              className="shrink-0 text-xs px-3 py-1.5 rounded-lg
                         bg-purple-600 hover:bg-purple-500 text-white font-medium
                         transition-colors flex items-center gap-1.5"
            >
              Watch <span aria-hidden>→</span>
            </button>
          </div>
          {transcriptBtn && (
            <div className="pt-0.5">{transcriptBtn}</div>
          )}
        </div>

        {showModal && transcript && (
          <TranscriptModal
            transcript={transcript}
            solution={solution ?? undefined}
            onClose={closeModal}
          />
        )}
      </>
    );
  }

  /* Failed */
  if (isFailed) {
    return (
      <div className="rounded-xl border border-[var(--wrong-bd)] bg-[var(--wrong-bg)] px-4 py-3 flex items-center gap-2.5">
        <XCircle size={16} className="text-[var(--red)] shrink-0" />
        <div>
          <p className="text-[var(--tx2)] text-sm font-medium">Video generation failed</p>
          <p className="text-[var(--tx7)] text-[10px] mt-0.5">Try again from the chat</p>
        </div>
      </div>
    );
  }

  /* In progress */
  return (
    <>
      <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 px-4 py-3.5">
        {/* Header */}
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-3.5 h-3.5 rounded-full bg-purple-500 animate-pulse shrink-0" />
          <p className="text-[var(--tx2)] text-sm font-semibold">Generating video…</p>
          <span className="ml-auto text-[var(--tx8)] text-[10px]">~2 min</span>
        </div>

        {/* Steps */}
        <div className="space-y-1.5 ml-1">
          {VIDEO_STEPS.map((step, i) => {
            const done   = i < stepIdx;
            const active = i === stepIdx;
            return (
              <div key={i} className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 transition-all ${
                  done   ? 'bg-green-500' :
                  active ? 'bg-purple-500 animate-pulse' :
                           'bg-[var(--ov3)]'
                }`}>
                  {done   && <CheckCircle size={9} className="text-white" />}
                  {active && <Loader size={8} className="text-white animate-spin" />}
                </div>
                <span className={`text-xs transition-colors ${
                  done   ? 'text-[var(--tx8)] line-through' :
                  active ? 'text-[var(--tx2)]' :
                           'text-[var(--tx9)]'
                }`}>
                  {step}
                </span>
              </div>
            );
          })}
        </div>

        {/* Transcript button — appears once script is ready (stage 1 done) */}
        {transcriptBtn && (
          <div className="mt-3 pt-3 border-t border-purple-500/15">
            {transcriptBtn}
          </div>
        )}
      </div>

      {showModal && transcript && (
        <TranscriptModal
          transcript={transcript}
          solution={solution ?? undefined}
          onClose={closeModal}
        />
      )}
    </>
  );
}

/* ── MessageBubble ──────────────────────────────────────────────────────────── */
interface MessageBubbleProps {
  message: Message;
  onChipClick?: (chip: string) => void;
  onMakeVisual?: (content: string, subject?: string) => void;
  onTestYourself?: (content: string, subject?: string) => void;
  onSimplify?: () => void;
  onGoDeeper?: () => void;
  /** Set when video generation has been triggered for this message */
  videoId?: number;
  /** Auth token forwarded to VideoStatusCard for polling */
  token?: string;
}

export function MessageBubble({
  message, onChipClick, onMakeVisual, onTestYourself, onSimplify, onGoDeeper,
  videoId, token,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const { t } = useTranslation();
  const isUser  = message.role === 'user';
  const subject = message.metadata?.subject;
  const aiChips = message.metadata?.chips ?? [];

  function copy() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  /* ── User bubble ──────────────────────────────────────────────── */
  if (isUser) {
    const imageUrl = message.metadata?.imageUrl;
    return (
      <div className="flex justify-end mb-5">
        <div
          className="max-w-[78%] rounded-2xl rounded-tr-sm overflow-hidden shadow-md shadow-purple-900/20"
          style={{ background: 'linear-gradient(135deg,#7c3aed,#6d28d9)' }}
        >
          {imageUrl && (
            <div className="px-3 pt-3 pb-1">
              <img
                src={imageUrl}
                alt="Selected PDF region"
                className="rounded-xl max-h-56 w-auto object-contain border border-white/20 bg-black/20"
                style={{ maxWidth: '100%' }}
              />
              <p className="text-white/50 text-[10px] mt-1.5 flex items-center gap-1">
                <span>📄</span> PDF region
              </p>
            </div>
          )}
          <div className="px-4 py-3 text-sm leading-relaxed text-white font-medium">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  /* ── AI bubble ────────────────────────────────────────────────── */
  return (
    <div className="flex gap-3 mb-6 items-start">
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-500 to-blue-500
                      flex items-center justify-center text-white text-xs font-bold shrink-0 mt-1">
        AI
      </div>

      <div className="flex-1 min-w-0">
        {subject?.subject && (
          <div className="mb-2">
            <SubjectBadge subject={subject.subject} subtopic={subject.subtopic} />
          </div>
        )}

        <div className="rounded-2xl rounded-tl-sm bg-[var(--surface)] border border-[var(--bd)]
                        shadow-lg shadow-black/10 px-5 py-4">
          {message.metadata?.quiz_id ? (
            <QuizCard
              quizId={message.metadata.quiz_id}
              topic={message.metadata.quiz_topic ?? message.content}
              numQuestions={message.metadata.num_questions}
            />
          ) : (
            <div className="ai-content">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {preprocessMath(message.content)}
              </ReactMarkdown>
            </div>
          )}

          {!message.metadata?.quiz_id && (
            <div className="mt-4 pt-3 border-t border-[var(--bd2)]">
              {/* Inline video status card */}
              {videoId != null && (
                <div className="mb-3">
                  <VideoStatusCard videoId={videoId} token={token} />
                </div>
              )}

              {/* Primary actions */}
              <div className="flex flex-wrap gap-2 items-center">
                {videoId == null && (
                  <MakeVisualButton
                    subject={subject?.subject ?? null}
                    onClick={() => onMakeVisual?.(message.content, subject?.subject)}
                  />
                )}
                <button
                  onClick={() => onTestYourself?.(message.content, subject?.subject)}
                  className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium transition-all
                             bg-indigo-500/10 hover:bg-indigo-500/20 text-[var(--indigo)]
                             border border-indigo-500/20"
                >
                  ✏️ Quiz me
                </button>

                <button
                  onClick={copy}
                  title="Copy"
                  className="ml-auto text-[var(--txa)] hover:text-[var(--tx4)] transition-colors p-1 rounded-lg hover:bg-[var(--ov1)]"
                >
                  {copied
                    ? <Check size={14} className="text-[var(--green)]" />
                    : <Copy size={14} />}
                </button>
              </div>

              {/* Suggestion chips */}
              <div className="mt-3 flex flex-wrap gap-2">
                {aiChips.map((chip, i) => (
                  <button
                    key={i}
                    onClick={() => onChipClick?.(chip)}
                    className="text-xs px-3 py-1.5 rounded-full transition-all
                               border border-[var(--bd)] hover:border-[var(--bd2)]
                               text-[var(--tx5)] hover:text-[var(--tx2)] hover:bg-[var(--ov1)]"
                  >
                    {chip}
                  </button>
                ))}
                <button
                  onClick={() => onChipClick?.('Give me a concrete real-world example of this')}
                  className="text-xs px-3 py-1.5 rounded-full transition-all
                             border border-amber-500/20 hover:border-amber-500/35
                             text-[var(--amber)] hover:text-[var(--amber)]"
                >
                  💡 Show me an example
                </button>
              </div>

              {/* Tertiary actions */}
              <div className="mt-3 flex gap-4">
                <button
                  onClick={onSimplify}
                  className="text-[11px] text-[var(--tx8)] hover:text-[var(--tx4)] transition-colors flex items-center gap-1"
                >
                  <span>↓</span> {t.chat.simplify}
                </button>
                <button
                  onClick={onGoDeeper}
                  className="text-[11px] text-[var(--tx8)] hover:text-[var(--tx4)] transition-colors flex items-center gap-1"
                >
                  <span>↑</span> {t.chat.goDeeper}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
