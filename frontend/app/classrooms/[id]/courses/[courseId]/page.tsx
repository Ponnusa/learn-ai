'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, ChevronDown, ChevronRight,
  CheckCircle2, Circle, Loader2, BookOpen, Zap,
  MessageSquare, Send,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Concept {
  id: string;
  title: string;
  description?: string;
  study_set_id?: string;
  visited: boolean;
  quiz_score?: number;
}

interface Unit {
  id: string;
  title: string;
  description?: string;
  position: number;
  concepts: Concept[];
}

interface Course {
  id: string;
  name: string;
  description?: string;
  subject?: string;
  grade?: string;
  status: string;
  progress: { visited: number; total: number };
  units: Unit[];
}

interface DqbQuestion {
  id: string;
  question: string;
  status: 'wondering' | 'getting_there' | 'understood';
  student_name: string;
  student_id: string;
  is_own: boolean;
  created_at: string;
}

const STATUS_NEXT: Record<string, string> = {
  wondering:    'getting_there',
  getting_there: 'understood',
  understood:   'wondering',
};

const STATUS_LABEL: Record<string, string> = {
  wondering:    '?',
  getting_there: '✓',
  understood:   '✓✓',
};

const STATUS_CLASSES: Record<string, string> = {
  wondering:    'bg-amber-500/15 text-amber-400 border-amber-500/25',
  getting_there: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
  understood:   'bg-green-500/15 text-green-400 border-green-500/25',
};

export default function StudentCoursePage() {
  const router      = useRouter();
  const params      = useParams();
  const classroomId = params.id       as string;
  const courseId    = params.courseId as string;
  const { user, token } = useSessionStore();

  const { t, tF } = useTranslation();
  const [course,      setCourse]    = useState<Course | null>(null);
  const [loading,     setLoading]   = useState(true);
  const [expanded,    setExpanded]  = useState<Set<string>>(new Set());
  const [curriculum,  setCurriculum] = useState<{
    driving_question?: string;
    teks_codes?: string[];
    active_lesson?: number;
    lesson_count?: number;
  } | null>(null);

  // DQB state
  const [dqbQuestions, setDqbQuestions] = useState<DqbQuestion[]>([]);
  const [dqbInput,     setDqbInput]     = useState('');
  const [dqbPosting,   setDqbPosting]   = useState(false);
  const [dqbLoading,   setDqbLoading]   = useState(false);
  const [updatingId,   setUpdatingId]   = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    load();
  }, [user, courseId]);

  async function load() {
    setLoading(true);
    try {
      const [courseRes, currRes] = await Promise.all([
        fetch(`${API_BASE}/api/courses/${courseId}/student`, { headers }),
        fetch(`${API_BASE}/api/courses/${courseId}/curriculum-context`),
      ]);
      if (!courseRes.ok) { router.push(`/classrooms/${classroomId}`); return; }
      const data: Course = await courseRes.json();
      setCourse(data);
      if (data.units.length > 0) setExpanded(new Set([data.units[0].id]));
      if (currRes.ok) {
        const ctx = await currRes.json();
        if (ctx.driving_question) setCurriculum(ctx);
      }
    } finally { setLoading(false); }
    loadDqb();
  }

  async function loadDqb() {
    setDqbLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/dqb/${classroomId}/${courseId}`, { headers });
      if (res.ok) setDqbQuestions(await res.json());
    } finally { setDqbLoading(false); }
  }

  async function postDqbQuestion() {
    const q = dqbInput.trim();
    if (!q || dqbPosting) return;
    setDqbPosting(true);
    try {
      const res = await fetch(`${API_BASE}/api/dqb/${classroomId}/${courseId}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ question: q }),
      });
      if (res.ok) {
        const newQ = await res.json();
        setDqbQuestions(prev => [...prev, {
          ...newQ,
          student_name: user?.name?.split(' ')[0] || 'Me',
          is_own: true,
        }]);
        setDqbInput('');
      }
    } finally { setDqbPosting(false); }
  }

  async function cycleStatus(q: DqbQuestion) {
    if (!q.is_own || updatingId) return;
    const nextStatus = STATUS_NEXT[q.status];
    setUpdatingId(q.id);
    try {
      const res = await fetch(`${API_BASE}/api/dqb/questions/${q.id}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ status: nextStatus }),
      });
      if (res.ok) {
        setDqbQuestions(prev => prev.map(x => x.id === q.id ? { ...x, status: nextStatus as DqbQuestion['status'] } : x));
      }
    } finally { setUpdatingId(null); }
  }

  function toggleUnit(id: string) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function openConcept(concept: Concept) {
    router.push(`/classrooms/${classroomId}/courses/${courseId}/concepts/${concept.id}`);
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  if (!course) return null;

  const pct = course.progress.total > 0
    ? Math.round((course.progress.visited / course.progress.total) * 100)
    : 0;

  const wonderingCount    = dqbQuestions.filter(q => q.status === 'wondering').length;
  const gettingThereCount = dqbQuestions.filter(q => q.status === 'getting_there').length;
  const understoodCount   = dqbQuestions.filter(q => q.status === 'understood').length;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      {/* Back link */}
      <button onClick={() => router.push(`/classrooms/${classroomId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> {t.classrooms.backToCourses}
      </button>

      {/* Course header */}
      <div className="mb-6">
        <h1 className="text-[var(--tx1)] text-2xl font-bold">{course.name}</h1>
        {course.description && (
          <p className="text-[var(--tx6)] text-sm mt-1">{course.description}</p>
        )}
        <div className="flex items-center gap-3 mt-1 text-xs text-[var(--tx7)]">
          {course.subject && <span>{course.subject}</span>}
          {course.grade   && <span>{course.grade}</span>}
          <span><BookOpen size={10} className="inline mr-0.5" />{tF(t.classrooms.unitsCount, { n: course.units.length })}</span>
        </div>
      </div>

      {/* Driving Question Banner */}
      {curriculum?.driving_question && (
        <div className="mb-4 rounded-xl border border-green-500/20 bg-green-500/5 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-green-400 mb-1">Driving Question</p>
          <p className="text-[var(--tx2)] text-sm leading-snug">{curriculum.driving_question}</p>
          {curriculum.teks_codes && curriculum.teks_codes.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {curriculum.teks_codes.map(code => (
                <span key={code}
                  className="text-xs px-2 py-0.5 rounded-md bg-green-500/10 text-green-400 border border-green-500/20 font-mono">
                  {code}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Progress bar */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[var(--tx3)] text-sm font-medium">{t.classrooms.yourProgress}</span>
          <span className="text-purple-400 text-sm font-bold">{pct}%</span>
        </div>
        <div className="h-2 bg-[var(--ov2)] rounded-full overflow-hidden">
          <div className="h-full bg-purple-500 rounded-full transition-all"
            style={{ width: `${pct}%` }} />
        </div>
        <p className="text-[var(--tx8)] text-xs mt-1.5">
          {tF(t.classrooms.conceptsVisited, { visited: course.progress.visited, total: course.progress.total })}
        </p>
      </div>

      {/* Units accordion */}
      <div className="space-y-2 mb-8">
        {course.units.map((unit, idx) => {
          const open       = expanded.has(unit.id);
          const unitVisited = unit.concepts.filter(c => c.visited).length;
          const unitTotal   = unit.concepts.length;

          return (
            <div key={unit.id}
              className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">
              <button
                onClick={() => toggleUnit(unit.id)}
                className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[var(--ov1)] transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-[var(--tx7)] text-xs font-mono shrink-0">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[var(--tx1)] font-semibold truncate">{unit.title}</p>
                    <p className="text-[var(--tx7)] text-xs mt-0.5">
                      {tF(t.classrooms.unitProgress, { done: unitVisited, total: unitTotal })}
                    </p>
                  </div>
                </div>
                {open
                  ? <ChevronDown size={16} className="text-[var(--tx7)] shrink-0" />
                  : <ChevronRight size={16} className="text-[var(--tx7)] shrink-0" />}
              </button>

              {open && (
                <div className="border-t border-[var(--bd)] divide-y divide-[var(--bd)]">
                  {unit.concepts.length === 0 ? (
                    <p className="px-5 py-4 text-[var(--tx7)] text-sm italic">{t.classrooms.noConceptsYet}</p>
                  ) : unit.concepts.map(concept => {
                    return (
                      <button key={concept.id}
                        onClick={() => openConcept(concept)}
                        className="w-full text-left flex items-start gap-3 px-5 py-3.5
                                   hover:bg-[var(--ov1)] transition-colors">
                        {concept.visited ? (
                          <CheckCircle2 size={16} className="text-green-400 shrink-0 mt-0.5" />
                        ) : (
                          <Circle size={16} className="text-[var(--tx8)] shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium ${concept.visited ? 'text-[var(--tx3)]' : 'text-[var(--tx1)]'}`}>
                            {concept.title}
                          </p>
                          {concept.description && (
                            <p className="text-[var(--tx7)] text-xs mt-0.5 line-clamp-1">
                              {concept.description}
                            </p>
                          )}
                          {concept.quiz_score !== undefined && concept.quiz_score !== null && (
                            <p className="text-xs text-amber-400 mt-0.5">
                              {tF(t.classrooms.quizScore, { pct: Math.round(concept.quiz_score!) })}
                            </p>
                          )}
                        </div>
                        <Zap size={13} className="text-[var(--tx8)] shrink-0 mt-0.5" />
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Driving Question Board */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-[var(--bd)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare size={16} className="text-purple-400" />
            <span className="text-[var(--tx1)] font-semibold text-sm">Question Board</span>
          </div>
          {dqbQuestions.length > 0 && (
            <div className="flex items-center gap-2 text-xs text-[var(--tx7)]">
              {wonderingCount    > 0 && <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">{wonderingCount} ?</span>}
              {gettingThereCount > 0 && <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">{gettingThereCount} ✓</span>}
              {understoodCount   > 0 && <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">{understoodCount} ✓✓</span>}
            </div>
          )}
        </div>

        {/* Post a question */}
        <div className="px-5 py-3 border-b border-[var(--bd)]">
          <div className="flex gap-2">
            <input
              value={dqbInput}
              onChange={e => setDqbInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && postDqbQuestion()}
              maxLength={500}
              placeholder="What are you still wondering about?"
              className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2
                         text-sm text-[var(--tx1)] placeholder:text-[var(--tx8)]
                         focus:outline-none focus:border-purple-500/50"
            />
            <button
              onClick={postDqbQuestion}
              disabled={!dqbInput.trim() || dqbPosting}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-purple-600 text-white text-sm
                         font-medium hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
              {dqbPosting
                ? <Loader2 size={14} className="animate-spin" />
                : <Send size={14} />}
            </button>
          </div>
        </div>

        {/* Questions list */}
        <div className="divide-y divide-[var(--bd)]">
          {dqbLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="text-purple-400 animate-spin" />
            </div>
          ) : dqbQuestions.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <MessageSquare size={28} className="text-[var(--tx8)] mx-auto mb-2" />
              <p className="text-[var(--tx7)] text-sm">No questions yet. Be the first to wonder!</p>
            </div>
          ) : dqbQuestions.map(q => (
            <div key={q.id} className="flex items-start gap-3 px-5 py-3.5">
              {/* Status badge — clickable if own question */}
              <button
                onClick={() => cycleStatus(q)}
                disabled={!q.is_own || updatingId === q.id}
                title={q.is_own ? 'Tap to update your understanding' : undefined}
                className={`shrink-0 mt-0.5 min-w-[2rem] text-center px-1.5 py-0.5 rounded border text-xs font-bold
                            ${STATUS_CLASSES[q.status]}
                            ${q.is_own ? 'cursor-pointer hover:opacity-80 transition-opacity' : 'cursor-default'}
                            ${updatingId === q.id ? 'opacity-50' : ''}`}>
                {updatingId === q.id
                  ? <Loader2 size={10} className="animate-spin inline" />
                  : STATUS_LABEL[q.status]}
              </button>

              {/* Question text + name */}
              <div className="flex-1 min-w-0">
                <p className="text-[var(--tx2)] text-sm leading-snug">{q.question}</p>
                <p className="text-[var(--tx8)] text-xs mt-0.5">
                  {q.is_own ? 'You' : q.student_name}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        {dqbQuestions.length > 0 && (
          <div className="px-5 py-2.5 border-t border-[var(--bd)] flex items-center gap-4 text-xs text-[var(--tx8)]">
            <span><span className="text-amber-400 font-bold">?</span> Still wondering</span>
            <span><span className="text-blue-400 font-bold">✓</span> Getting there</span>
            <span><span className="text-green-400 font-bold">✓✓</span> Understood</span>
            <span className="ml-auto italic">Tap your badge to update</span>
          </div>
        )}
      </div>
    </div>
  );
}
