'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, Users, GraduationCap, Loader2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface InstOverview {
  id: string;
  name: string;
  plan: string;
  max_teachers: number;
  max_students: number;
  teacher_count: number;
  student_count: number;
}

export default function InstitutionDashboard() {
  const router = useRouter();
  const { user, token } = useSessionStore();
  const [inst,    setInst]    = useState<InstOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    if (!['institution_admin', 'super_admin'].includes(user.account_type ?? '')) {
      router.replace('/');
      return;
    }
    loadInstitution();
  }, [user]);

  async function loadInstitution() {
    try {
      // Fetch the institution this admin belongs to
      const res = await fetch(`${API_BASE}/api/institutions/mine`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setInst(await res.json());
    } catch {
      // Institution endpoint not yet wired for /mine — will be added in Sprint 1
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <Loader2 size={32} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-[var(--tx1)] text-2xl font-bold">
            {inst?.name ?? 'Institution Dashboard'}
          </h1>
          <p className="text-[var(--tx6)] text-sm mt-1">
            Plan: <span className="capitalize text-purple-400">{inst?.plan ?? '—'}</span>
          </p>
        </div>

        {inst && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
            {[
              { label: 'Teachers',      value: `${inst.teacher_count} / ${inst.max_teachers}`, icon: GraduationCap },
              { label: 'Students',      value: `${inst.student_count} / ${inst.max_students}`, icon: Users },
              { label: 'Institution',   value: inst.plan,                                       icon: Building2 },
            ].map(s => (
              <div key={s.label} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
                <s.icon size={20} className="text-purple-400 mb-2" />
                <p className="text-[var(--tx1)] text-lg font-bold">{s.value}</p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          {[
            { label: 'Manage Teachers', icon: GraduationCap, href: '/institution/teachers', soon: true },
            { label: 'Manage Students', icon: Users,         href: '/institution/students', soon: true },
          ].map(card => (
            <button
              key={card.label}
              className="p-5 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl text-left opacity-50 cursor-not-allowed"
            >
              <card.icon size={22} className="text-purple-400 mb-3" />
              <p className="text-[var(--tx1)] text-sm font-medium">{card.label}</p>
              <p className="text-[var(--tx7)] text-xs mt-0.5">Coming in Sprint 1</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
