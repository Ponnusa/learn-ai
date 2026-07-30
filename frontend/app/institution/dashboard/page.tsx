'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, Users, GraduationCap, Loader2, Globe } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { LANGUAGE_LABELS } from '@/translations';
import type { LanguageCode } from '@/translations';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface InstOverview {
  id: string;
  name: string;
  plan: string;
  language: string | null;
  max_teachers: number;
  max_students: number;
  teacher_count: number;
  student_count: number;
}

const LANG_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '',   label: 'No lock — users choose freely' },
  { value: 'en', label: '🇬🇧 English' },
  { value: 'fi', label: '🇫🇮 Suomi' },
  { value: 'sv', label: '🇸🇪 Svenska' },
  { value: 'es', label: '🇪🇸 Español' },
  { value: 'fr', label: '🇫🇷 Français' },
];

export default function InstitutionDashboard() {
  const router = useRouter();
  const { user, token, setInstitutionLanguage } = useSessionStore();
  const [inst,         setInst]         = useState<InstOverview | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [langValue,    setLangValue]    = useState('');
  const [savingLang,   setSavingLang]   = useState(false);
  const [langSaved,    setLangSaved]    = useState(false);

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
      const res = await fetch(`${API_BASE}/api/institutions/mine`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setInst(data);
        setLangValue(data.language ?? '');
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function saveLanguage() {
    if (!token) return;
    setSavingLang(true);
    try {
      const res = await fetch(`${API_BASE}/api/institutions/mine/language`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: langValue || null }),
      });
      if (res.ok) {
        const data = await res.json();
        setInst(prev => prev ? { ...prev, language: data.language } : prev);
        setInstitutionLanguage(data.language);
        setLangSaved(true);
        setTimeout(() => setLangSaved(false), 2000);
      }
    } finally {
      setSavingLang(false);
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

        {/* Language setting */}
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-4">
          <div className="flex items-center gap-2 mb-3">
            <Globe size={18} className="text-purple-400" />
            <p className="text-[var(--tx1)] text-sm font-semibold">Institution Language</p>
          </div>
          <p className="text-[var(--tx7)] text-xs mb-4">
            When set, all teachers and students in this institution will have this language applied automatically. Leave empty to let users choose their own.
          </p>
          <div className="flex items-center gap-3">
            <select
              value={langValue}
              onChange={e => setLangValue(e.target.value)}
              className="flex-1 bg-[var(--input)] border border-[var(--bd)] text-[var(--tx2)] text-sm rounded-xl px-3 py-2 outline-none focus:border-purple-500"
            >
              {LANG_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button
              onClick={saveLanguage}
              disabled={savingLang || langValue === (inst?.language ?? '')}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-all disabled:opacity-40 min-w-[80px]"
            >
              {savingLang ? <Loader2 size={14} className="animate-spin mx-auto" /> : langSaved ? '✓ Saved' : 'Save'}
            </button>
          </div>
        </div>

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
