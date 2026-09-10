import { useState } from 'react';
import { submitQuiz, type QuizQuestion, type SubmitQuizResponse } from '../lib/api';

interface GenieQuizProps {
  quizId: string;
  questions: QuizQuestion[];
  userId?: string | null;
  token?: string | null;
  onClose: () => void;
}

// Minimal inline quiz — no navigation, no card-in-chat-thread complexity
// (frontend/components/chat/MessageBubble.tsx's QuizCard uses next/navigation
// to push to a full /quiz/{id} page; the panel just renders it in place).
export function GenieQuiz({ quizId, questions, userId, token, onClose }: GenieQuizProps) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<SubmitQuizResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allAnswered = questions.every((_, i) => answers[i] !== undefined);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitQuiz(quizId, answers, userId, token);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not submit the quiz');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-4 mb-2 p-3 rounded-xl border border-[var(--bd)] bg-[var(--surface)] flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-[var(--tx1)]">
          🎯 Quiz {result && `— ${result.correct}/${result.total} (${Math.round(result.score_pct)}%)`}
        </span>
        <button
          type="button"
          aria-label="Close quiz"
          className="text-[var(--tx7)] hover:text-[var(--tx1)] text-sm leading-none"
          onClick={onClose}
        >
          ✕
        </button>
      </div>

      {questions.map((q, i) => {
        const qResult = result?.results[i];
        return (
          <div key={i} className="flex flex-col gap-1.5">
            <p className="text-xs font-medium text-[var(--tx2)]">
              {i + 1}. {q.q}
            </p>
            <div className="flex flex-col gap-1">
              {q.options.map((opt, oi) => {
                const selected = answers[i] === oi;
                const isCorrectOption = result && oi === qResult?.correct_index;
                const isWrongSelected = result && selected && !qResult?.correct;
                return (
                  <button
                    key={oi}
                    type="button"
                    disabled={!!result}
                    onClick={() => setAnswers((prev) => ({ ...prev, [i]: oi }))}
                    className="text-left text-xs px-2.5 py-1.5 rounded-lg border transition-colors"
                    style={{
                      borderColor: isCorrectOption
                        ? 'var(--green, #4ade80)'
                        : isWrongSelected
                          ? 'var(--red)'
                          : selected
                            ? 'var(--indigo)'
                            : 'var(--bd)',
                      background: isCorrectOption
                        ? 'rgba(34,197,94,0.08)'
                        : isWrongSelected
                          ? 'rgba(239,68,68,0.08)'
                          : selected
                            ? 'rgba(129,140,248,0.10)'
                            : 'transparent',
                      color: 'var(--tx2)',
                    }}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
            {result && (
              <p className="text-[11px] text-[var(--tx7)] leading-snug pl-0.5">{q.explanation}</p>
            )}
          </div>
        );
      })}

      {error && <p className="text-xs text-[var(--red)]">{error}</p>}

      {!result && (
        <button
          type="button"
          disabled={!allAnswered || submitting}
          onClick={handleSubmit}
          className="self-start text-xs font-medium px-3 py-1.5 rounded-lg bg-[var(--indigo)] text-white disabled:opacity-50"
        >
          {submitting ? 'Submitting…' : 'Submit answers'}
        </button>
      )}
    </div>
  );
}
