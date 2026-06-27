'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Loader2, BarChart2, Users, AlertTriangle } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface CourseProgress {
  id: string; name: string; status: string;
  student_count: number; concept_count: number; failed_count: number;
  visited_pct: number | null; avg_quiz_score: number | null;
}

export default function TeacherProgressOverviewPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();

  const [courses, setCourses] = useState<CourseProgress[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/progress-overview`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setCourses(await res.json());
    } finally { setLoading(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-[var(--tx1)] text-2xl font-bold">Student Progress</h1>
        <p className="text-[var(--tx6)] text-sm mt-1">Across all your courses — pick one to see the full per-student grid</p>
      </div>

      {courses.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mx-auto mb-4">
            <BarChart2 size={28} className="text-[var(--tx7)]" />
          </div>
          <p className="text-[var(--tx3)] font-medium mb-1">No courses yet</p>
          <p className="text-[var(--tx7)] text-sm">Create a course to start tracking student progress</p>
        </div>
      ) : (
        <div className="space-y-3">
          {courses.map(c => (
            <button key={c.id} onClick={() => router.push(`/teacher/courses/${c.id}/progress`)}
              className="w-full text-left bg-[var(--surface)] border border-[var(--bd)]
                         hover:border-purple-500/30 rounded-2xl p-5 transition-all group">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <h3 className="text-[var(--tx1)] font-semibold">{c.name}</h3>
                    {c.failed_count > 0 && (
                      <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-500/15 text-red-400">
                        <AlertTriangle size={10} /> {c.failed_count} failed
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-[var(--tx7)]">
                    <span className="flex items-center gap-1"><Users size={11} /> {c.student_count} students</span>
                    <span>{c.concept_count} concepts</span>
                    <span>
                      {c.visited_pct !== null ? `${c.visited_pct}% visited` : 'No activity yet'}
                    </span>
                    {c.avg_quiz_score !== null && (
                      <span className={
                        c.avg_quiz_score >= 70 ? 'text-green-400' : c.avg_quiz_score >= 40 ? 'text-amber-400' : 'text-red-400'
                      }>{c.avg_quiz_score}% avg quiz</span>
                    )}
                  </div>
                </div>
                <ArrowRight size={16} className="text-[var(--tx8)] group-hover:text-purple-400 transition-colors shrink-0 mt-1" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
