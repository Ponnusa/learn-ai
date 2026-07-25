'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Users, BookOpen, ArrowRight, Loader2, LogIn, Layers, HelpCircle } from 'lucide-react';
import { StudentClassroomsTour } from '@/components/onboarding/StudentClassroomsTour';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Classroom {
  id: string;
  name: string;
  subject?: string;
  grade?: string;
  join_code: string;
  is_active: boolean;
  student_count: number;
  teacher_name?: string;
  teacher_email?: string;
  due_flashcards: number;
}

export default function StudentClassroomsPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();
  const { t, tF } = useTranslation();

  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [code,       setCode]       = useState('');
  const [joining,    setJoining]    = useState(false);
  const [joinMsg,    setJoinMsg]    = useState('');
  const [joinErr,    setJoinErr]    = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    load();
  }, [user]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/enrolled`, { headers });
      if (res.ok) {
        setClassrooms(await res.json());
      } else {
        console.error('enrolled fetch failed', res.status, await res.text());
      }
    } finally {
      setLoading(false);
    }
  }

  async function joinClassroom(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setJoining(true); setJoinMsg(''); setJoinErr('');
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/join`, {
        method: 'POST', headers,
        body: JSON.stringify({ code: code.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Invalid code');
      setJoinMsg(data.message);
      setCode('');
      load();
    } catch (err: any) {
      setJoinErr(err.message);
    } finally {
      setJoining(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <Loader2 size={28} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-2xl mx-auto">

        <StudentClassroomsTour />
        <div className="mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-[var(--tx1)] text-2xl font-bold">{t.classrooms.title}</h1>
              <p className="text-[var(--tx6)] text-sm mt-1">{t.classrooms.subtitle}</p>
            </div>
            <button
              onClick={() => window.dispatchEvent(new CustomEvent('start-student-classrooms-tour'))}
              className="text-[var(--tx7)] hover:text-purple-400 transition-colors p-1 mt-1"
              title="Take a tour"
            ><HelpCircle size={14} /></button>
          </div>
        </div>

        {(() => {
          const totalDue = classrooms.reduce((sum, c) => sum + c.due_flashcards, 0);
          return totalDue > 0 ? (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 mb-6 flex items-center gap-3">
              <Layers size={18} className="text-amber-400 shrink-0" />
              <p className="text-amber-300 text-sm">
                {tF(t.classrooms.flashcardsDue, { n: totalDue })}
              </p>
            </div>
          ) : null;
        })()}

        {/* Join form */}
        <form onSubmit={joinClassroom}
          className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-8">
          <p className="text-[var(--tx2)] text-sm font-medium mb-3">Join a classroom</p>
          <div className="flex gap-2">
            <input
              data-tour="join-code-input"
              placeholder={t.classrooms.joinCodePlaceholder}
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase())}
              maxLength={6}
              className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-2.5
                         text-sm text-[var(--tx1)] font-mono tracking-widest uppercase
                         outline-none focus:border-purple-500/60 transition-colors"
            />
            <button type="submit" disabled={joining || code.length < 4}
              className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-500
                         text-white text-sm font-medium rounded-xl transition-all disabled:opacity-40">
              {joining ? <Loader2 size={14} className="animate-spin" /> : <><LogIn size={14} /> {t.classrooms.join}</>}
            </button>
          </div>
          {joinMsg && <p className="text-green-400 text-xs mt-2">{joinMsg}</p>}
          {joinErr && <p className="text-red-400 text-xs mt-2">{joinErr}</p>}
        </form>

        {/* Enrolled classrooms */}
        {classrooms.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mx-auto mb-4">
              <Users size={28} className="text-[var(--tx7)]" />
            </div>
            <p className="text-[var(--tx3)] font-medium mb-1">{t.classrooms.noClassrooms}</p>
            <p className="text-[var(--tx7)] text-sm">{t.classrooms.noClassroomsHint}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {classrooms.map(cls => (
              <button key={cls.id}
                onClick={() => router.push(`/classrooms/${cls.id}`)}
                className="w-full text-left bg-[var(--surface)] border border-[var(--bd)]
                           hover:border-purple-500/30 rounded-2xl p-5 transition-all group">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-[var(--tx1)] font-semibold mb-1">{cls.name}</h3>
                    <div className="flex items-center gap-3 flex-wrap text-xs text-[var(--tx6)]">
                      {cls.subject && <span className="flex items-center gap-1"><BookOpen size={11} /> {cls.subject}</span>}
                      {cls.grade   && <span>{cls.grade}</span>}
                      <span className="flex items-center gap-1"><Users size={11} /> {tF(t.classrooms.studentsCount, { n: cls.student_count })}</span>
                    </div>
                    {(cls.teacher_name || cls.teacher_email) && (
                      <p className="text-[var(--tx7)] text-xs mt-2">
                        {tF(t.classrooms.teacherLabel, { name: cls.teacher_name ?? cls.teacher_email ?? '' })}
                      </p>
                    )}
                    {cls.due_flashcards > 0 && (
                      <span className="inline-flex items-center gap-1 mt-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-2 py-0.5">
                        <Layers size={10} /> {tF(t.classrooms.dueCount, { n: cls.due_flashcards })}
                      </span>
                    )}
                  </div>
                  <ArrowRight size={16} className="text-[var(--tx8)] group-hover:text-purple-400 transition-colors shrink-0 mt-1" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
