import { useState } from 'react';
import { submitQuiz, type QuizQuestion, type SubmitQuizResponse } from '../lib/api';
import { MathText } from '../components/MathText';

interface GenieQuizProps {
  quizId: string;
  questions: QuizQuestion[];
  userId?: string | null;
  token?: string | null;
}

// Minimal inline quiz — no navigation, no card-in-chat-thread complexity
// (frontend/components/chat/MessageBubble.tsx's QuizCard uses next/navigation
// to push to a full /quiz/{id} page; the panel just renders it in place).
//
// Behaves like a message in the conversation, not a dialog: there's no
// "close" that discards the quiz and its result — only minimize/expand.
// Minimized shows just the score line; expanded shows every question with
// the student's answers and mistakes highlighted. Auto-minimizes right
// after a successful submit (the completed quiz settles into a summary,
// same as it would read in an actual conversation), but can be expanded
// again at any time to review what was missed.
export function GenieQuiz({ quizId, questions, userId, token }: GenieQuizProps) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<SubmitQuizResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const allAnswered = questions.every((_, i) => answers[i] !== undefined);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitQuiz(quizId, answers, userId, token);
      setResult(res);
      setCollapsed(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not submit the quiz');
    } finally {
      setSubmitting(false);
    }
  }

  const summary = result
    ? `🎯 Quiz — ${result.correct}/${result.total} (${Math.round(result.score_pct)}%)`
    : '🎯 Quiz (in progress)';

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="mx-4 mb-2 flex items-center justify-between px-3 py-2 rounded-xl border border-[var(--bd)] bg-[var(--surface)] text-left"
      >
        <span className="text-sm font-medium text-[var(--tx1)]">{summary}</span>
        <span className="text-[var(--tx7)] text-xs" aria-hidden="true">
          Expand ⌄
        </span>
      </button>
    );
  }

  return (
    <div className="mx-4 mb-2 p-3 rounded-xl border border-[var(--bd)] bg-[var(--surface)] flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-[var(--tx1)]">{summary}</span>
        <button
          type="button"
          aria-label="Minimize quiz"
          title="Minimize"
          className="text-[var(--tx7)] hover:text-[var(--tx1)] text-xs leading-none"
          onClick={() => setCollapsed(true)}
        >
          Minimize ⌃
        </button>
      </div>

      {questions.map((q, i) => {
        const qResult = result?.results[i];
        return (
          <div key={i} className="flex flex-col gap-1.5">
            <p className="text-xs font-medium text-[var(--tx2)]">
              {i + 1}. <MathText inline>{q.q}</MathText>
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
                    <MathText inline>{opt}</MathText>
                  </button>
                );
              })}
            </div>
            {result && (
              <p className="text-[11px] text-[var(--tx7)] leading-snug pl-0.5">
                <MathText inline>{q.explanation}</MathText>
              </p>
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
