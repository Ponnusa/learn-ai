'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, Loader2, CheckCircle2, Circle } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ConceptProgress { id: string; title: string; visited: boolean; quiz_score: number | null; }
interface CourseProgress  { id: string; name: string; concepts: ConceptProgress[]; }
interface StudentProgress { id: string; name: string; email: string; courses: CourseProgress[]; }

export default function TeacherStudentDetailPage() {
  const router    = useRouter();
  const params    = useParams();
  const studentId = params.id as string;
  const { user, token } = useSessionStore();

  const [data,    setData]    = useState<StudentProgress | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user, studentId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/students/${studentId}/progress`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { router.replace('/teacher/students'); return; }
      setData(await res.json());
    } finally { setLoading(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!data) return null;

  return (
    <div className="p-6 max-w-3xl mx-auto pb-16">
      <button onClick={() => router.push('/teacher/students')}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> Back to students
      </button>

      <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{data.name ?? data.email}</h1>
      <p className="text-[var(--tx7)] text-sm mb-6">{data.email}</p>

      {data.courses.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">No courses assigned to this student's classrooms yet.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.courses.map(c => (
            <div key={c.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
              <h2 className="text-[var(--tx1)] font-semibold mb-3">{c.name}</h2>
              <div className="space-y-1.5">
                {c.concepts.map(concept => (
                  <div key={concept.id} className="flex items-center gap-3 text-sm py-1">
                    {concept.visited
                      ? <CheckCircle2 size={14} className="text-green-400 shrink-0" />
                      : <Circle size={14} className="text-[var(--tx8)] shrink-0" />}
                    <span className="flex-1 text-[var(--tx2)]">{concept.title}</span>
                    {concept.quiz_score !== null && (
                      <span className={
                        concept.quiz_score >= 70 ? 'text-green-400' : concept.quiz_score >= 40 ? 'text-amber-400' : 'text-red-400'
                      }>{Math.round(concept.quiz_score)}%</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
