'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, BookOpen, Layers, FileText, Loader2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Course {
  id: string;
  name: string;
  description?: string;
  subject?: string;
  grade?: string;
  unit_count: number;
  concept_count: number;
  visited_count: number;
}

export default function StudentClassroomPage() {
  const router  = useRouter();
  const params  = useParams();
  const classroomId = params.id as string;
  const { user, token } = useSessionStore();

  const [courses,  setCourses]  = useState<Course[]>([]);
  const [loading,  setLoading]  = useState(true);

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    load();
  }, [user, classroomId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}/courses`, { headers });
      if (res.ok) setCourses(await res.json());
    } finally { setLoading(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <button onClick={() => router.push('/classrooms')}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> My classrooms
      </button>

      <div className="mb-8">
        <h1 className="text-[var(--tx1)] text-2xl font-bold">Courses</h1>
        <p className="text-[var(--tx6)] text-sm mt-1">{courses.length} course{courses.length !== 1 ? 's' : ''} assigned by your teacher</p>
      </div>

      {courses.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mx-auto mb-4">
            <BookOpen size={28} className="text-[var(--tx7)]" />
          </div>
          <p className="text-[var(--tx3)] font-medium mb-1">No courses yet</p>
          <p className="text-[var(--tx7)] text-sm">Your teacher hasn't assigned any courses to this classroom yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {courses.map(c => {
            const pct = c.concept_count > 0
              ? Math.round((c.visited_count / c.concept_count) * 100)
              : 0;
            return (
              <button key={c.id}
                onClick={() => router.push(`/classrooms/${classroomId}/courses/${c.id}`)}
                className="w-full text-left bg-[var(--surface)] border border-[var(--bd)]
                           hover:border-purple-500/30 rounded-2xl p-5 transition-all group">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-[var(--tx1)] font-semibold">{c.name}</h3>
                    {c.description && <p className="text-[var(--tx6)] text-sm mt-0.5 line-clamp-1">{c.description}</p>}
                    <div className="flex items-center gap-3 mt-1 text-xs text-[var(--tx7)]">
                      {c.subject && <span>{c.subject}</span>}
                      {c.grade   && <span>{c.grade}</span>}
                      <span className="flex items-center gap-1"><Layers size={10} /> {c.unit_count} units</span>
                      <span className="flex items-center gap-1"><FileText size={10} /> {c.concept_count} concepts</span>
                    </div>
                  </div>
                  <span className="text-purple-400 text-sm font-bold shrink-0">{pct}%</span>
                </div>

                {/* Progress bar */}
                <div className="h-1.5 bg-[var(--ov2)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-[var(--tx8)] text-xs mt-1.5">
                  {c.visited_count} of {c.concept_count} concepts visited
                </p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
