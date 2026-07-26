'use client';
import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, Loader2, HelpCircle, Layers, Video, BookOpen, CheckCircle2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Course  { id: string; name: string; }
interface Concept { id: string; title: string; }
interface Unit    { id: string; title: string; concepts: Concept[]; }

export default function BulkAssignPage() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={28} className="text-purple-400 animate-spin" />
      </div>
    }>
      <BulkAssignContent />
    </Suspense>
  );
}

function BulkAssignContent() {
  const router = useRouter();
  const search  = useSearchParams();
  const studentIds = (search.get('ids') ?? '').split(',').filter(Boolean);
  const { user, token } = useSessionStore();
  const { t, tF } = useTranslation();

  const KIND_LABEL: Record<string, { label: string; icon: typeof HelpCircle }> = {
    quiz:       { label: t.teacher.kindQuiz,       icon: HelpCircle },
    flashcards: { label: t.teacher.kindFlashcards, icon: Layers },
    video:      { label: t.teacher.kindVideo,      icon: Video },
    studyset:   { label: t.teacher.kindStudySet,   icon: BookOpen },
  };

  const [courses,  setCourses]  = useState<Course[]>([]);
  const [units,     setUnits]    = useState<Unit[]>([]);
  const [courseId,  setCourseId] = useState('');
  const [conceptId, setConceptId] = useState('');
  const [loading,   setLoading]  = useState(true);
  const [assigning, setAssigning] = useState<string | null>(null);
  const [done,      setDone]      = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    loadCourses();
  }, [user]);

  async function loadCourses() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/mine`, { headers });
      if (res.ok) {
        const data = await res.json();
        setCourses(data);
        if (data[0]) { setCourseId(data[0].id); loadConcepts(data[0].id); }
      }
    } finally { setLoading(false); }
  }

  async function loadConcepts(cid: string) {
    setCourseId(cid);
    setConceptId('');
    const res = await fetch(`${API_BASE}/api/courses/${cid}`, { headers });
    if (res.ok) {
      const course = await res.json();
      setUnits(course.units ?? []);
      const first = course.units?.[0]?.concepts?.[0]?.id;
      if (first) setConceptId(first);
    }
  }

  async function assignToAll(kind: string) {
    if (!conceptId || studentIds.length === 0) return;
    setAssigning(kind);
    setDone(null);
    try {
      await Promise.all(studentIds.map(sid =>
        fetch(`${API_BASE}/api/assignments`, {
          method: 'POST', headers,
          body: JSON.stringify({ student_id: sid, concept_id: conceptId, kind }),
        }).catch(() => {})
      ));
      setDone(kind);
    } finally { setAssigning(null); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <button onClick={() => router.push('/teacher/students')}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> {t.teacher.backToStudents}
      </button>

      <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{t.teacher.assignTitle}</h1>
      <p className="text-[var(--tx7)] text-sm mb-6">{tF(t.teacher.selectedStudents, { n: studentIds.length })}</p>

      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 space-y-3">
        <select value={courseId} onChange={e => loadConcepts(e.target.value)}
          className="w-full bg-[var(--input)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                     text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors">
          {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <select value={conceptId} onChange={e => setConceptId(e.target.value)}
          className="w-full bg-[var(--input)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                     text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors">
          {units.map(u => (
            <optgroup key={u.id} label={u.title}>
              {u.concepts.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
            </optgroup>
          ))}
        </select>

        <div className="flex gap-2 flex-wrap pt-1">
          {Object.entries(KIND_LABEL).map(([kind, { label, icon: Icon }]) => (
            <button key={kind} onClick={() => assignToAll(kind)} disabled={!!assigning || !conceptId}
              className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-xl border border-[var(--bd)]
                         text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all disabled:opacity-50">
              {assigning === kind ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
              {label}
            </button>
          ))}
        </div>

        {done && (
          <p className="text-green-400 text-sm flex items-center gap-1.5 pt-1">
            <CheckCircle2 size={14} /> {tF(t.teacher.assignedSuccess, { kind: KIND_LABEL[done].label.toLowerCase(), n: studentIds.length })}
          </p>
        )}
      </div>
    </div>
  );
}
