'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { GraduationCap, Users, Layers, BookOpen, Loader2, ChevronRight } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DashSection {
  id: string; name: string; grade: string | null; section_label: string | null;
  teacher: { name: string; email: string } | null;
  student_count: number;
  courses: { course_id: string; course_name: string; subject: string | null }[];
}
interface Dashboard {
  school: { name: string; city: string; country: string; code: string };
  stats: { teachers: number; students: number; sections: number; courses: number };
  sections: DashSection[];
}

export default function SchoolAdminDashboard() {
  const router = useRouter();
  const { user, token } = useSessionStore();
  const [data,    setData]    = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/school/dashboard`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setData(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  const stats = data?.stats;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-[var(--tx1)] text-2xl font-bold">
          {data?.school.name ?? 'Dashboard'}
        </h1>
        <p className="text-[var(--tx6)] text-sm mt-1">
          {[data?.school.city, data?.school.country].filter(Boolean).join(', ')}
          {data?.school.code && (
            <span className="ml-2 inline-block px-2 py-0.5 rounded-full bg-purple-600/20 text-purple-300 text-xs font-mono">
              {data.school.code}
            </span>
          )}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Teachers',  value: stats?.teachers ?? 0, icon: GraduationCap, href: '/school-admin/teachers' },
          { label: 'Students',  value: stats?.students ?? 0, icon: Users,         href: '/school-admin/students' },
          { label: 'Sections',  value: stats?.sections ?? 0, icon: Layers,        href: '/school-admin/sections' },
          { label: 'Courses',   value: stats?.courses  ?? 0, icon: BookOpen,      href: '/school-admin/courses'  },
        ].map(s => (
          <button
            key={s.label}
            onClick={() => router.push(s.href)}
            className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 text-left
                       hover:border-purple-500/40 transition-colors group"
          >
            <s.icon size={20} className="text-purple-400 mb-2" />
            <p className="text-[var(--tx1)] text-xl font-bold">{s.value}</p>
            <p className="text-[var(--tx7)] text-xs mt-0.5">{s.label}</p>
          </button>
        ))}
      </div>

      {/* Sections */}
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-[var(--tx1)] font-semibold">Sections</h2>
        <button
          onClick={() => router.push('/school-admin/sections')}
          className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1"
        >
          Manage <ChevronRight size={13} />
        </button>
      </div>

      {(!data?.sections || data.sections.length === 0) ? (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 text-center">
          <Layers size={32} className="text-[var(--tx7)] mx-auto mb-3" />
          <p className="text-[var(--tx5)] text-sm">No sections yet.</p>
          <button
            onClick={() => router.push('/school-admin/sections')}
            className="mt-3 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-colors"
          >
            Create a Section
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {data.sections.map(s => (
            <div
              key={s.id}
              className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-[var(--tx1)] font-semibold text-sm">{s.name}</p>
                  {s.grade && (
                    <span className="text-xs text-[var(--tx7)]">Grade {s.grade}</span>
                  )}
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--ov2)] text-[var(--tx5)]">
                  {s.student_count} students
                </span>
              </div>

              {s.teacher ? (
                <p className="text-xs text-[var(--tx6)] mb-3">
                  Teacher: <span className="text-[var(--tx3)]">{s.teacher.name}</span>
                </p>
              ) : (
                <p className="text-xs text-amber-400 mb-3">No teacher assigned</p>
              )}

              {s.courses.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {s.courses.map(c => (
                    <span
                      key={c.course_id}
                      className="text-xs px-2 py-0.5 rounded-full bg-purple-600/15 text-purple-300"
                    >
                      {c.course_name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--tx7)]">No courses assigned</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
