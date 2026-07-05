'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, Users, Copy, Check, Trash2, Loader2, UserX } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Student {
  id: string;
  email: string;
  name?: string;
  joined_at: string;
  last_seen_at?: string;
}

interface Classroom {
  id: string;
  name: string;
  subject?: string;
  grade?: string;
  join_code: string;
  is_active: boolean;
  student_count: number;
  students: Student[];
}

export default function ClassroomDetailPage() {
  const router  = useRouter();
  const params  = useParams();
  const classroomId = params.id as string;
  const { user, token } = useSessionStore();

  const { t, tF } = useTranslation();
  const [cls,       setCls]       = useState<Classroom | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [copied,    setCopied]    = useState(false);
  const [removing,  setRemoving]  = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user, classroomId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}`, { headers });
      if (!res.ok) { router.replace('/teacher/classrooms'); return; }
      setCls(await res.json());
    } finally {
      setLoading(false);
    }
  }

  async function removeStudent(studentId: string) {
    setRemoving(studentId);
    try {
      await fetch(`${API_BASE}/api/classrooms/${classroomId}/students/${studentId}`, {
        method: 'DELETE', headers,
      });
      setCls(prev => prev ? {
        ...prev,
        students: prev.students.filter(s => s.id !== studentId),
        student_count: prev.student_count - 1,
      } : prev);
    } finally {
      setRemoving(null);
    }
  }

  async function toggleArchive() {
    if (!cls) return;
    setArchiving(true);
    try {
      await fetch(`${API_BASE}/api/classrooms/${classroomId}`, {
        method: 'PATCH', headers,
        body: JSON.stringify({ is_active: !cls.is_active }),
      });
      setCls(prev => prev ? { ...prev, is_active: !prev.is_active } : prev);
    } finally {
      setArchiving(false);
    }
  }

  function copyCode() {
    if (!cls) return;
    navigator.clipboard.writeText(cls.join_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <Loader2 size={28} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  if (!cls) return null;

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-3xl mx-auto">

        {/* Back */}
        <button onClick={() => router.push('/teacher/classrooms')}
          className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
          <ArrowLeft size={15} /> {t.teacher.backToClassrooms}
        </button>

        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-[var(--tx1)] text-2xl font-bold">{cls.name}</h1>
              {!cls.is_active && (
                <span className="text-xs px-2 py-0.5 bg-[var(--ov1)] text-[var(--tx7)] rounded-full">{t.teacher.archived}</span>
              )}
            </div>
            <p className="text-[var(--tx6)] text-sm mt-1">
              {[cls.subject, cls.grade].filter(Boolean).join(' · ')}
              {cls.student_count > 0 && ` · ${cls.student_count} student${cls.student_count !== 1 ? 's' : ''}`}
            </p>
          </div>
          <button
            onClick={toggleArchive}
            disabled={archiving}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--bd)] hover:border-[var(--tx6)]
                       text-[var(--tx6)] hover:text-[var(--tx2)] text-xs rounded-xl transition-all disabled:opacity-40"
          >
            {archiving ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
            {cls.is_active ? t.teacher.archiveClassroom : t.teacher.reopenClassroom}
          </button>
        </div>

        {/* Join code */}
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
          <p className="text-[var(--tx6)] text-xs mb-1">{t.teacher.studentJoinCode}</p>
          <div className="flex items-center justify-between">
            <p className="text-purple-400 font-mono text-3xl font-bold tracking-[0.25em]">{cls.join_code}</p>
            <button onClick={copyCode}
              className="flex items-center gap-1.5 px-3 py-2 bg-purple-600/15 hover:bg-purple-600/25
                         text-purple-400 text-sm rounded-xl transition-all">
              {copied ? <><Check size={14} /> {t.teacher.copied}</> : <><Copy size={14} /> {t.teacher.copyCode}</>}
            </button>
          </div>
          <p className="text-[var(--tx8)] text-xs mt-3">
            Students go to the app → Classrooms → Enter code <strong className="text-[var(--tx6)]">{cls.join_code}</strong>
          </p>
        </div>

        {/* Student roster */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Users size={16} className="text-[var(--tx6)]" />
            <h2 className="text-[var(--tx1)] font-semibold">
              {tF(t.teacher.studentsCountLabel, { n: cls.student_count })}
            </h2>
          </div>

          {cls.students.length === 0 ? (
            <div className="text-center py-12 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl">
              <Users size={32} className="text-[var(--tx8)] mx-auto mb-3" />
              <p className="text-[var(--tx5)] text-sm">{t.teacher.noStudents}</p>
              <p className="text-[var(--tx7)] text-xs mt-1">{t.teacher.noStudentsHint}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {cls.students.map(s => (
                <div key={s.id}
                  className="flex items-center gap-4 p-4 bg-[var(--surface)] border border-[var(--bd)] rounded-xl">
                  <div className="w-8 h-8 rounded-full bg-purple-600/20 flex items-center justify-center shrink-0">
                    <span className="text-purple-400 text-xs font-bold">
                      {(s.name ?? s.email)[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--tx1)] text-sm font-medium truncate">{s.name ?? s.email}</p>
                    {s.name && <p className="text-[var(--tx7)] text-xs truncate">{s.email}</p>}
                    <p className="text-[var(--tx8)] text-xs mt-0.5">
                      {tF(t.teacher.joinedDate, { date: new Date(s.joined_at).toLocaleDateString() })}
                      {s.last_seen_at && ` · ${tF(t.teacher.lastSeenDate, { date: new Date(s.last_seen_at).toLocaleDateString() })}`}
                    </p>
                  </div>
                  <button
                    onClick={() => removeStudent(s.id)}
                    disabled={removing === s.id}
                    title={t.teacher.removeStudent}
                    className="text-[var(--tx8)] hover:text-red-400 transition-colors disabled:opacity-40 shrink-0"
                  >
                    {removing === s.id
                      ? <Loader2 size={15} className="animate-spin" />
                      : <UserX size={15} />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
