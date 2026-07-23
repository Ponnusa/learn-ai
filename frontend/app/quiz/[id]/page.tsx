'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react';
import { submitQuiz, getQuiz } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';

interface Question {
  q: string;
  options: string[];
  correct: number;
  explanation?: string;
}

interface QuizResult {
  correct: number;
  total: number;
  score_pct: number;
  passed: boolean;
  results: {
    question: string;
    options: string[];
    correct: number;
    user_answer: number;
    is_correct: boolean;
    explanation: string;
  }[];
}

// Renders any string that may contain LaTeX ($...$, $$...$$) or plain text.
// Uses a custom <p> renderer so the output stays inline inside buttons/spans.
function MathText({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
      components={{ p: ({ children }) => <span>{children}</span> }}
    >
      {preprocessMath(children ?? '')}
    </ReactMarkdown>
  );
}

export default function QuizPage() {
  const params   = useParams();
  const router   = useRouter();
  const { t, tF } = useTranslation();
  const { token, user } = useSessionStore();

  const searchParams = useSearchParams();
  const quizId = params.id as string;
  // Return destination — defaults to home if not specified
  const fromUrl = searchParams.get('from') ?? '/';

  const [questions,        setQuestions]        = useState<Question[]>([]);
  const [currentIdx,       setCurrentIdx]       = useState(0);
  const [selected,         setSelected]         = useState<number | null>(null);
  const [answers,          setAnswers]          = useState<Record<string, number>>({});
  const [showExplanation,  setShowExplanation]  = useState(false);
  const [results,          setResults]          = useState<QuizResult | null>(null);
  const [submitting,       setSubmitting]       = useState(false);
  const [notFound,         setNotFound]         = useState(false);
  const [loadingQuiz,      setLoadingQuiz]      = useState(true);

  useEffect(() => {
    if (!quizId) return;

    const stored = localStorage.getItem(`quiz_${quizId}`);
    if (stored) {
      try {
        const parsed: Question[] = JSON.parse(stored);
        if (parsed.length > 0) {
          setQuestions(parsed);
          setLoadingQuiz(false);
          return;
        }
      } catch { /* fall through to API */ }
    }

    getQuiz(quizId, token ?? undefined)
      .then(res => {
        if (res.completed) {
          const qs          = res.questions ?? [];
          const userAnswers = res.user_answers ?? {};
          const correct     = res.score     ?? 0;
          const total       = res.max_score ?? qs.length;
          setQuestions(qs);
          setResults({
            correct,
            total,
            score_pct: total > 0 ? Math.round((correct / total) * 100) : 0,
            passed:    total > 0 && (correct / total) >= 0.7,
            results: qs.map((q: any, i: number) => {
              const qCorrect = Number(q.correct);
              const rawAns   = userAnswers[String(i)];
              const userAns  = rawAns != null ? Number(rawAns) : -1;
              return {
                question:    q.q,
                options:     q.options,
                correct:     qCorrect,
                user_answer: userAns,
                is_correct:  userAns !== -1 && userAns === qCorrect,
                explanation: q.explanation ?? '',
              };
            }),
          });
          return;
        }
        if (!res.questions || res.questions.length === 0) {
          setNotFound(true);
        } else {
          setQuestions(res.questions);
        }
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoadingQuiz(false));
  }, [quizId]);

  const currentQ = questions[currentIdx];
  const isLast   = currentIdx === questions.length - 1;
  const answered = selected !== null;

  function handleSelect(optIdx: number) {
    if (answered) return;
    setSelected(optIdx);
    setShowExplanation(true);
  }

  async function handleNext() {
    if (selected === null) return;
    const newAnswers = { ...answers, [String(currentIdx)]: selected };
    setAnswers(newAnswers);

    if (isLast) {
      setSubmitting(true);
      try {
        const res = await submitQuiz(quizId, newAnswers, user?.id, token ?? undefined);
        setResults(res);
        localStorage.removeItem(`quiz_${quizId}`);
      } catch {
        const total   = questions.length;
        const localResults = questions.map((q, i) => {
          const qCorrect = Number(q.correct);
          const rawAns   = newAnswers[String(i)];
          const userAns  = rawAns != null ? Number(rawAns) : -1;
          return {
            question:    q.q,
            options:     q.options,
            correct:     qCorrect,
            user_answer: userAns,
            is_correct:  userAns !== -1 && userAns === qCorrect,
            explanation: q.explanation ?? '',
          };
        });
        const correct = localResults.filter(r => r.is_correct).length;
        setResults({
          correct,
          total,
          score_pct: Math.round((correct / total) * 100),
          passed: (correct / total) >= 0.7,
          results: localResults,
        });
        localStorage.removeItem(`quiz_${quizId}`);
      } finally {
        setSubmitting(false);
      }
    } else {
      setCurrentIdx(prev => prev + 1);
      setSelected(null);
      setShowExplanation(false);
    }
  }

  /* ── Not found ──────────────────────────────────────────────────── */
  if (notFound) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-[var(--tx5)] mb-4">{t.quiz.notFound}</p>
          <button
            onClick={() => router.push(fromUrl)}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-sm transition-colors"
          >
            {t.back}
          </button>
        </div>
      </div>
    );
  }

  /* ── Loading ────────────────────────────────────────────────────── */
  if (loadingQuiz) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  /* ── Results screen ─────────────────────────────────────────────── */
  if (results) {
    return (
      <div className="min-h-screen bg-[var(--bg)] p-4">
        <div className="max-w-2xl mx-auto pt-8 pb-12">
          {/* Score summary */}
          <div className="text-center mb-10">
            <div className="text-6xl mb-4">{results.passed ? '🎉' : '📚'}</div>
            <h1 className="text-[var(--tx1)] text-2xl font-bold mb-2">
              {results.passed ? t.quiz.wellDone : t.quiz.keepPracticing}
            </h1>
            <p className="text-[var(--tx5)] text-sm">
              {tF(t.quiz.score, { score: results.correct, total: results.total })}
            </p>
            <p className="text-4xl font-bold text-[var(--purple)] mt-3">{results.score_pct}%</p>
          </div>

          {/* Per-question review */}
          <div className="space-y-4">
            {results.results.map((r, i) => (
              <div
                key={i}
                className={`rounded-2xl border p-4 ${
                  r.is_correct
                    ? 'border-[var(--correct-bd)] bg-[var(--correct-bg)]'
                    : 'border-[var(--wrong-bd)]   bg-[var(--wrong-bg)]'
                }`}
              >
                <div className="flex gap-3 mb-3">
                  {r.is_correct
                    ? <CheckCircle size={18} className="text-[var(--green)] shrink-0 mt-0.5" />
                    : <XCircle    size={18} className="text-[var(--red)]   shrink-0 mt-0.5" />
                  }
                  <div className="text-[var(--tx1)] text-sm font-medium">
                    <MathText>{r.question}</MathText>
                  </div>
                </div>
                <div className="ml-7 space-y-1">
                  {r.options.map((opt, j) => (
                    <div
                      key={j}
                      className={`text-xs px-3 py-1.5 rounded-lg ${
                        j === Number(r.correct)
                          ? 'bg-[var(--correct-bg)] text-[var(--green)] border border-[var(--correct-bd)]'
                          : j === Number(r.user_answer) && !r.is_correct
                          ? 'bg-[var(--wrong-bg)]   text-[var(--red)]   border border-[var(--wrong-bd)]'
                          : 'text-[var(--tx8)]'
                      }`}
                    >
                      <MathText>{opt}</MathText>
                    </div>
                  ))}
                </div>
                {r.explanation && (
                  <div className="ml-7 mt-3 text-xs text-[var(--tx6)] italic">
                    <MathText>{r.explanation}</MathText>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex justify-center gap-3 mt-8">
            <button
              onClick={() => router.push(fromUrl)}
              className="px-5 py-2.5 bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx1)] text-sm rounded-xl transition-colors"
            >
              {t.back}
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ── Question screen ────────────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--bd)]">
        <button onClick={() => router.push(fromUrl)} className="text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-[var(--tx1)] font-semibold">{t.quiz.title}</h1>
        <span className="ml-auto text-[var(--tx6)] text-sm">
          {tF(t.quiz.question, { n: currentIdx + 1, total: questions.length })}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-[var(--ov1)]">
        <div
          className="h-1 bg-purple-500 transition-all duration-500"
          style={{ width: `${((currentIdx + (answered ? 1 : 0)) / questions.length) * 100}%` }}
        />
      </div>

      {/* Question */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-lg">
          <div className="text-[var(--tx1)] text-lg font-medium mb-8 leading-relaxed">
            <MathText>{currentQ.q}</MathText>
          </div>

          {/* Options */}
          <div className="space-y-3">
            {currentQ.options.map((opt, i) => {
              const isCorrect  = i === currentQ.correct;
              const isSelected = selected === i;

              let cls = 'border-[var(--bd)] bg-[var(--ov1)] text-[var(--tx2)] hover:border-[var(--bd2)] hover:bg-[var(--ov3)]';
              if (answered) {
                if (isCorrect)                     cls = 'border-[var(--correct-bd)] bg-[var(--correct-bg)] text-[var(--green)]';
                else if (isSelected && !isCorrect) cls = 'border-[var(--wrong-bd)]   bg-[var(--wrong-bg)]   text-[var(--red)]';
                else                               cls = 'border-[var(--bd3)] bg-transparent text-[var(--tx9)]';
              }

              return (
                <button
                  key={i}
                  onClick={() => handleSelect(i)}
                  className={`w-full text-left px-4 py-3.5 rounded-xl border transition-all text-sm ${cls}`}
                >
                  <span className="font-medium mr-2 text-[var(--tx6)]">
                    {String.fromCharCode(65 + i)}.
                  </span>
                  <MathText>{opt}</MathText>
                </button>
              );
            })}
          </div>

          {/* Explanation */}
          {showExplanation && currentQ.explanation && (
            <div className="mt-5 p-4 rounded-xl bg-[var(--ov1)] border border-[var(--bd)]">
              <p className="text-xs text-[var(--tx6)] uppercase tracking-wider mb-1.5">
                {t.quiz.explanation}
              </p>
              <div className="text-sm text-[var(--tx3)]">
                <MathText>{currentQ.explanation ?? ''}</MathText>
              </div>
            </div>
          )}

          {/* Next / Submit */}
          {answered && (
            <button
              onClick={handleNext}
              disabled={submitting}
              className="w-full mt-6 py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-medium rounded-xl transition-colors"
            >
              {submitting
                ? t.loading
                : isLast
                ? t.quiz.seeResults
                : t.quiz.nextQuestion}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
