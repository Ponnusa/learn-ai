'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, Users, GraduationCap, Loader2, Globe } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface InstOverview {
  id: string;
  name: string;
  plan: string;
  languages: string[] | null;
  max_teachers: number;
  max_students: number;
  teacher_count: number;
  student_count: number;
}

const LANG_OPTIONS: Array<{ code: string; label: string }> = [
  { code: 'en', label: '🇬🇧 English' },
  { code: 'fi', label: '🇫🇮 Suomi' },
  { code: 'sv', label: '🇸🇪 Svenska' },
  { code: 'es', label: '🇪🇸 Español' },
  { code: 'fr', label: '🇫🇷 Français' },
];

export default function InstitutionDashboard() {
  const router = useRouter();
  const { user, token, setInstitutionLanguages } = useSessionStore();
  const [inst,         setInst]         = useState<InstOverview | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [langValues,   setLangValues]   = useState<string[]>([]);
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
        setLangValues(data.languages ?? []);
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
        body: JSON.stringify({ languages: langValues.length ? langValues : null }),
      });
      if (res.ok) {
        const data = await res.json();
        const langs = data.languages ?? null;
        setInst(prev => prev ? { ...prev, languages: langs } : prev);
        setInstitutionLanguages(langs);
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
          <div className="flex items-center gap-2 mb-2">
            <Globe size={18} className="text-purple-400" />
            <p className="text-[var(--tx1)] text-sm font-semibold">Allowed Languages</p>
          </div>
          <p className="text-[var(--tx7)] text-xs mb-4">
            Check the languages members of this institution can use. Leave all unchecked to let users choose freely.
          </p>
          <div className="flex flex-wrap gap-4 mb-4">
            {LANG_OPTIONS.map(({ code, label }) => (
              <label key={code} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={langValues.includes(code)}
                  onChange={e => setLangValues(prev =>
                    e.target.checked ? [...prev, code] : prev.filter(l => l !== code)
                  )}
                  className="accent-purple-500 w-4 h-4"
                />
                <span className="text-[var(--tx2)] text-sm">{label}</span>
              </label>
            ))}
          </div>
          <button
            onClick={saveLanguage}
            disabled={savingLang}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-all disabled:opacity-40 min-w-[80px]"
          >
            {savingLang ? <Loader2 size={14} className="animate-spin mx-auto" /> : langSaved ? '✓ Saved' : 'Save'}
          </button>
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
