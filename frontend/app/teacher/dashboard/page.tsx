'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { GraduationCap, BookOpen, Users, BarChart2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

export default function TeacherDashboard() {
  const router = useRouter();
  const { user } = useSessionStore();

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    if (!['teacher', 'institution_admin', 'super_admin'].includes(user.account_type ?? '')) {
      router.replace('/');
    }
  }, [user]);

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-[var(--tx1)] text-2xl font-bold">Teacher Dashboard</h1>
          <p className="text-[var(--tx6)] text-sm mt-1">Welcome back, {user?.name ?? user?.email}</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'My Classrooms', icon: Users,         href: '/teacher/classrooms', soon: false },
            { label: 'Course Builder', icon: BookOpen,     href: '/teacher/courses',    soon: true },
            { label: 'Student Progress', icon: BarChart2,  href: '/teacher/progress',   soon: true },
            { label: 'Study Sets',     icon: GraduationCap, href: '/study',             soon: false },
          ].map(card => (
            <button
              key={card.label}
              onClick={() => !card.soon && router.push(card.href)}
              className={`relative p-5 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl text-left transition-all
                          ${card.soon ? 'opacity-50 cursor-not-allowed' : 'hover:border-purple-500/40'}`}
            >
              <card.icon size={22} className="text-purple-400 mb-3" />
              <p className="text-[var(--tx1)] text-sm font-medium">{card.label}</p>
              {card.soon && (
                <span className="absolute top-3 right-3 text-xs bg-[var(--ov1)] text-[var(--tx8)] px-2 py-0.5 rounded-full">
                  Coming soon
                </span>
              )}
            </button>
          ))}
        </div>

        <p className="text-[var(--tx7)] text-xs text-center mt-12">
          Sprint 1 features (classrooms, assignments, student tracking) are coming soon.
        </p>
      </div>
    </div>
  );
}
