'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react';
import { submitQuiz } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

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

export default function QuizPage() {
  const params   = useParams();
  const router   = useRouter();
  const { t, tF } = useTranslation();
  const { token, user } = useSessionStore();

  const quizId = params.id as string;

  const [questions,        setQuestions]        = useState<Question[]>([]);
  const [currentIdx,       setCurrentIdx]       = useState(0);
  const [selected,         setSelected]         = useState<number | null>(null);
  const [answers,          setAnswers]          = useState<Record<string, number>>({});
  const [showExplanation,  setShowExplanation]  = useState(false);
  const [results,          setResults]          = useState<QuizResult | null>(null);
  const [submitting,       setSubmitting]       = useState(false);
  const [notFound,         setNotFound]         = useState(false);

  // Questions are saved to localStorage by the chat page before navigation
  useEffect(() => {
    if (!quizId) return;
    const stored = localStorage.getItem(`quiz_${quizId}`);
    if (stored) {
      try { setQuestions(JSON.parse(stored)); }
      catch { setNotFound(true); }
    } else {
      setNotFound(true);
    }
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
        // Compute results locally as fallback
        const correct = Object.entries(newAnswers).filter(
          ([i, ans]) => ans === questions[Number(i)]?.correct
        ).length;
        const total   = questions.length;
        setResults({
          correct,
          total,
          score_pct: Math.round((correct / total) * 100),
          passed: (correct / total) >= 0.7,
          results: questions.map((q, i) => ({
            question:    q.q,
            options:     q.options,
            correct:     q.correct,
            user_answer: newAnswers[String(i)] ?? -1,
            is_correct:  newAnswers[String(i)] === q.correct,
            explanation: q.explanation ?? '',
          })),
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

  // ── Not found ──────────────────────────────────────────────────────────────
  if (notFound) {
    return (
      <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-white/50 mb-4">Quiz not found or session expired.</p>
          <button
            onClick={() => router.push('/')}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-sm transition-colors"
          >
            Back to chat
          </button>
        </div>
      </div>
    );
  }

  // ── Loading questions ──────────────────────────────────────────────────────
  if (questions.length === 0) {
    return (
      <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Results screen ─────────────────────────────────────────────────────────
  if (results) {
    return (
      <div className="min-h-screen bg-[#0f0f0f] p-4">
        <div className="max-w-2xl mx-auto pt-8 pb-12">
          {/* Score summary */}
          <div className="text-center mb-10">
            <div className="text-6xl mb-4">{results.passed ? '🎉' : '📚'}</div>
            <h1 className="text-white text-2xl font-bold mb-2">
              {results.passed ? t.quiz.wellDone : t.quiz.keepPracticing}
            </h1>
            <p className="text-white/50 text-sm">
              {tF(t.quiz.score, { score: results.correct, total: results.total })}
            </p>
            <p className="text-4xl font-bold text-purple-400 mt-3">{results.score_pct}%</p>
          </div>

          {/* Per-question review */}
          <div className="space-y-4">
            {results.results.map((r, i) => (
              <div
                key={i}
                className={`rounded-2xl border p-4 ${
                  r.is_correct
                    ? 'border-green-500/30 bg-green-500/5'
                    : 'border-red-500/30 bg-red-500/5'
                }`}
              >
                <div className="flex gap-3 mb-3">
                  {r.is_correct
                    ? <CheckCircle size={18} className="text-green-400 shrink-0 mt-0.5" />
                    : <XCircle    size={18} className="text-red-400   shrink-0 mt-0.5" />
                  }
                  <p className="text-white text-sm font-medium">{r.question}</p>
                </div>
                <div className="ml-7 space-y-1">
                  {r.options.map((opt, j) => (
                    <div
                      key={j}
                      className={`text-xs px-3 py-1.5 rounded-lg ${
                        j === r.correct
                          ? 'bg-green-500/20 text-green-300'
                          : j === r.user_answer && !r.is_correct
                          ? 'bg-red-500/20 text-red-300'
                          : 'text-white/30'
                      }`}
                    >
                      {opt}
                    </div>
                  ))}
                </div>
                {r.explanation && (
                  <p className="ml-7 mt-3 text-xs text-white/50 italic">{r.explanation}</p>
                )}
              </div>
            ))}
          </div>

          <div className="flex justify-center gap-3 mt-8">
            <button
              onClick={() => router.push('/')}
              className="px-5 py-2.5 bg-white/10 hover:bg-white/15 text-white text-sm rounded-xl transition-colors"
            >
              {t.back}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Question screen ────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#0f0f0f] flex flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-white/10">
        <button onClick={() => router.push('/')} className="text-white/50 hover:text-white transition-colors">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-white font-semibold">{t.quiz.title}</h1>
        <span className="ml-auto text-white/40 text-sm">
          {tF(t.quiz.question, { n: currentIdx + 1, total: questions.length })}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-white/5">
        <div
          className="h-1 bg-purple-500 transition-all duration-500"
          style={{ width: `${((currentIdx + (answered ? 1 : 0)) / questions.length) * 100}%` }}
        />
      </div>

      {/* Question */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-lg">
          <p className="text-white text-lg font-medium mb-8 leading-relaxed">{currentQ.q}</p>

          {/* Options */}
          <div className="space-y-3">
            {currentQ.options.map((opt, i) => {
              const isCorrect  = i === currentQ.correct;
              const isSelected = selected === i;

              let cls = 'border-white/10 bg-white/5 text-white/80 hover:border-white/20 hover:bg-white/10';
              if (answered) {
                if (isCorrect)                    cls = 'border-green-500 bg-green-500/10 text-green-300';
                else if (isSelected && !isCorrect) cls = 'border-red-500   bg-red-500/10   text-red-300';
                else                               cls = 'border-white/5  bg-transparent   text-white/25';
              }

              return (
                <button
                  key={i}
                  onClick={() => handleSelect(i)}
                  className={`w-full text-left px-4 py-3.5 rounded-xl border transition-all text-sm ${cls}`}
                >
                  <span className="font-medium mr-2 text-white/40">
                    {String.fromCharCode(65 + i)}.
                  </span>
                  {opt}
                </button>
              );
            })}
          </div>

          {/* Explanation */}
          {showExplanation && currentQ.explanation && (
            <div className="mt-5 p-4 rounded-xl bg-white/5 border border-white/10">
              <p className="text-xs text-white/40 uppercase tracking-wider mb-1.5">
                {t.quiz.explanation}
              </p>
              <p className="text-sm text-white/70">{currentQ.explanation}</p>
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
