'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Copy, Check } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { SubjectBadge } from './SubjectBadge';
import { MakeVisualButton } from './MakeVisualButton';
import { preprocessMath } from '@/lib/preprocessMath';
import { getQuiz } from '@/lib/api';

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
      {/* Header */}
      <div className="flex items-start gap-3">
        <span className="text-xl mt-0.5">📝</span>
        <div>
          <p className="text-[var(--tx2)] text-sm font-semibold leading-snug">{topic}</p>
          {numQuestions != null && (
            <p className="text-[var(--tx6)] text-xs mt-0.5">{numQuestions} questions</p>
          )}
        </div>
      </div>

      {/* Status + CTA */}
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

interface MessageBubbleProps {
  message: Message;
  onChipClick?: (chip: string) => void;
  onMakeVisual?: (content: string, subject?: string) => void;
  onTestYourself?: (content: string, subject?: string) => void;
  onSimplify?: () => void;
  onGoDeeper?: () => void;
}

export function MessageBubble({
  message, onChipClick, onMakeVisual, onTestYourself, onSimplify, onGoDeeper,
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
              {/* Primary actions */}
              <div className="flex flex-wrap gap-2 items-center">
                <MakeVisualButton
                  subject={subject?.subject ?? null}
                  onClick={() => onMakeVisual?.(message.content, subject?.subject)}
                />
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
