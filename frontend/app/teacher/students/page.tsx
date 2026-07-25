'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Loader2, GraduationCap, Layers, AlertTriangle, HelpCircle } from 'lucide-react';
import { TeacherStudentsTour } from '@/components/onboarding/TeacherStudentsTour';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Risk = 'at_risk' | 'watch' | 'ok';

interface StudentRow {
  id: string; name: string; email: string;
  classrooms: { id: string; name: string }[];
  concept_count: number; visited_pct: number | null;
  avg_quiz_score: number | null; due_flashcards: number;
  last_seen_at: string | null; risk: Risk;
}

export default function TeacherStudentsPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();
  const { t, tF } = useTranslation();

  const RISK_BADGE: Record<Risk, { label: string; cls: string; dot: string }> = {
    at_risk: { label: t.teacher.riskAt,    cls: 'bg-red-500/15 text-red-400',     dot: 'bg-red-400' },
    watch:   { label: t.teacher.riskWatch, cls: 'bg-amber-500/15 text-amber-400', dot: 'bg-amber-400' },
    ok:      { label: t.teacher.riskOnTrack, cls: 'bg-green-500/15 text-green-400', dot: 'bg-green-400' },
  };

  const [students, setStudents] = useState<StudentRow[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [atRiskOnly, setAtRiskOnly] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/students-overview`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setStudents(await res.json());
    } finally { setLoading(false); }
  }

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const visible = atRiskOnly ? students.filter(s => s.risk === 'at_risk') : students;

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-4xl mx-auto pb-16">
      <TeacherStudentsTour />
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-[var(--tx1)] text-2xl font-bold">{t.teacher.studentsTitle}</h1>
          <p className="text-[var(--tx6)] text-sm mt-1">{tF(t.teacher.studentsSubtitle, { n: students.length })}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('start-teacher-students-tour'))}
            className="text-[var(--tx7)] hover:text-purple-400 transition-colors p-1"
            title="Take a tour"
          ><HelpCircle size={14} /></button>
          <button
            data-tour="risk-filter"
            onClick={() => { setAtRiskOnly(v => !v); setSelected(new Set()); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border transition-all shrink-0 ${
              atRiskOnly
                ? 'border-red-500/40 text-red-400 bg-red-500/10'
                : 'border-[var(--bd)] text-[var(--tx6)] hover:border-red-500/30 hover:text-red-400'
            }`}>
            <AlertTriangle size={14} /> {t.teacher.atRiskOnly}
          </button>
        </div>
      </div>

      {selected.size > 0 && (
        <div className="bg-purple-500/10 border border-purple-500/20 rounded-2xl p-4 mb-4 flex items-center justify-between gap-3">
          <p className="text-purple-300 text-sm">{tF(t.teacher.selectedStudents, { n: selected.size })}</p>
          <button
            onClick={() => router.push(`/teacher/students/assign?ids=${[...selected].join(',')}`)}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-xl transition-all">
            {t.teacher.assignPractice}
          </button>
        </div>
      )}

      {visible.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mx-auto mb-4">
            <GraduationCap size={28} className="text-[var(--tx7)]" />
          </div>
          <p className="text-[var(--tx3)] font-medium mb-1">{atRiskOnly ? t.teacher.noAtRisk : t.teacher.noStudentsYet}</p>
          <p className="text-[var(--tx7)] text-sm">{atRiskOnly ? 'Nice work — check back as more data comes in' : 'Students will show up here once they join a classroom'}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {visible.map(s => {
            const badge = RISK_BADGE[s.risk];
            return (
              <div key={s.id}
                className="flex items-center gap-3 bg-[var(--surface)] border border-[var(--bd)]
                           hover:border-purple-500/30 rounded-2xl p-4 transition-all group">
                {atRiskOnly && (
                  <input type="checkbox" checked={selected.has(s.id)}
                    onChange={() => toggleSelect(s.id)}
                    className="w-4 h-4 shrink-0 accent-purple-500" />
                )}
                <button onClick={() => router.push(`/teacher/students/${s.id}`)}
                  className="flex-1 text-left flex items-start justify-between gap-4 min-w-0">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="text-[var(--tx1)] font-semibold truncate">{s.name ?? s.email}</h3>
                      <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${badge.cls}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} /> {badge.label}
                      </span>
                    </div>
                    <p className="text-[var(--tx7)] text-xs truncate mb-1">
                      {s.classrooms.map(c => c.name).join(', ')}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-[var(--tx7)] flex-wrap">
                      <span>{s.visited_pct !== null ? tF(t.teacher.pctVisited, { pct: s.visited_pct }) : t.teacher.noActivity}</span>
                      {s.avg_quiz_score !== null && (
                        <span className={
                          s.avg_quiz_score >= 70 ? 'text-green-400' : s.avg_quiz_score >= 40 ? 'text-amber-400' : 'text-red-400'
                        }>{tF(t.teacher.avgQuiz, { pct: s.avg_quiz_score })}</span>
                      )}
                      {s.due_flashcards > 0 && (
                        <span className="flex items-center gap-1 text-amber-400"><Layers size={10} /> {tF(t.teacher.dueReview, { n: s.due_flashcards })}</span>
                      )}
                      <span>{s.last_seen_at ? tF(t.teacher.lastActive, { date: new Date(s.last_seen_at).toLocaleDateString() }) : t.teacher.neverActive}</span>
                    </div>
                  </div>
                  <ArrowRight size={16} className="text-[var(--tx8)] group-hover:text-purple-400 transition-colors shrink-0 mt-1" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
