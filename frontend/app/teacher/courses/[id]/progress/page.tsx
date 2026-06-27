'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, Loader2, Users, CheckCircle2, Circle } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Cell    { visited: boolean; quiz_score: number | null; }
interface Concept  { id: string; title: string; unit_title: string; }
interface StudentRow {
  id: string; name: string; email: string;
  visited_count: number; avg_quiz_score: number | null;
  cells: Record<string, Cell>;
}
interface ProgressData {
  course_id: string; course_name: string;
  concepts: Concept[]; students: StudentRow[];
}

export default function CourseProgressPage() {
  const router   = useRouter();
  const params   = useParams();
  const courseId = params.id as string;
  const { user, token } = useSessionStore();

  const [data,    setData]    = useState<ProgressData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user, courseId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/progress`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { router.replace(`/teacher/courses/${courseId}`); return; }
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
    <div className="p-6 max-w-5xl mx-auto pb-16">

      <button onClick={() => router.push(`/teacher/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> Back to course
      </button>

      <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{data.course_name}</h1>
      <p className="text-[var(--tx7)] text-sm mb-6 flex items-center gap-1.5">
        <Users size={13} /> {data.students.length} student{data.students.length === 1 ? '' : 's'} · {data.concepts.length} concepts
      </p>

      {data.students.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">No students enrolled yet — assign this course to a classroom with students.</p>
        </div>
      ) : data.concepts.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">No concepts yet — add units and concepts to this course first.</p>
        </div>
      ) : (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-[var(--bd)]">
                <th className="text-left p-3 text-[var(--tx7)] font-medium sticky left-0 bg-[var(--surface)]">Student</th>
                <th className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap">Visited</th>
                <th className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap">Avg quiz</th>
                {data.concepts.map(c => (
                  <th key={c.id} className="text-center p-3 text-[var(--tx7)] font-medium whitespace-nowrap max-w-[120px]" title={c.title}>
                    <div className="truncate">{c.title}</div>
                    <div className="text-[var(--tx8)] text-[10px] font-normal truncate">{c.unit_title}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.students.map(s => (
                <tr key={s.id} className="border-b border-[var(--bd)] last:border-0 hover:bg-[var(--ov1)]">
                  <td className="p-3 sticky left-0 bg-[var(--surface)]">
                    <p className="text-[var(--tx1)] font-medium">{s.name}</p>
                    <p className="text-[var(--tx8)] text-xs">{s.email}</p>
                  </td>
                  <td className="text-center p-3 text-[var(--tx2)] whitespace-nowrap">
                    {s.visited_count}/{data.concepts.length}
                  </td>
                  <td className="text-center p-3 whitespace-nowrap">
                    {s.avg_quiz_score !== null ? (
                      <span className={`font-medium ${
                        s.avg_quiz_score >= 70 ? 'text-green-400' : s.avg_quiz_score >= 40 ? 'text-amber-400' : 'text-red-400'
                      }`}>{Math.round(s.avg_quiz_score)}%</span>
                    ) : <span className="text-[var(--tx8)]">—</span>}
                  </td>
                  {data.concepts.map(c => {
                    const cell = s.cells[c.id];
                    return (
                      <td key={c.id} className="text-center p-3">
                        {cell?.visited ? (
                          <div className="flex flex-col items-center gap-0.5">
                            <CheckCircle2 size={14} className="text-green-400" />
                            {cell.quiz_score !== null && (
                              <span className="text-[10px] text-[var(--tx7)]">{Math.round(cell.quiz_score)}%</span>
                            )}
                          </div>
                        ) : (
                          <Circle size={14} className="text-[var(--tx8)] mx-auto" />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
