'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Users, BookOpen, ArrowRight, Loader2, Copy, Check } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Classroom {
  id: string;
  name: string;
  subject?: string;
  grade?: string;
  join_code: string;
  is_active: boolean;
  student_count: number;
  created_at: string;
}

export default function TeacherClassroomsPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();

  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [creating,   setCreating]   = useState(false);
  const [showForm,   setShowForm]   = useState(false);
  const [name,       setName]       = useState('');
  const [subject,    setSubject]    = useState('');
  const [grade,      setGrade]      = useState('');
  const [copiedId,   setCopiedId]   = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    if (!['teacher', 'institution_admin', 'super_admin'].includes(user.account_type ?? '')) {
      router.replace('/'); return;
    }
    load();
  }, [user]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/teaching`, { headers });
      if (res.ok) setClassrooms(await res.json());
    } finally {
      setLoading(false);
    }
  }

  async function createClassroom(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms`, {
        method: 'POST', headers,
        body: JSON.stringify({ name: name.trim(), subject: subject || undefined, grade: grade || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setClassrooms(prev => [data, ...prev]);
      setName(''); setSubject(''); setGrade('');
      setShowForm(false);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  }

  function copyCode(code: string, id: string) {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  const inputCls = `w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-2.5
                    text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors`;

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <Loader2 size={28} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-3xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-[var(--tx1)] text-2xl font-bold">My Classrooms</h1>
            <p className="text-[var(--tx6)] text-sm mt-1">{classrooms.length} classroom{classrooms.length !== 1 ? 's' : ''}</p>
          </div>
          <button
            onClick={() => setShowForm(s => !s)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                       text-white text-sm font-medium rounded-xl transition-all"
          >
            <Plus size={16} /> New classroom
          </button>
        </div>

        {/* Create form */}
        {showForm && (
          <form onSubmit={createClassroom}
            className="bg-[var(--surface)] border border-purple-500/30 rounded-2xl p-5 mb-6 space-y-3">
            <p className="text-[var(--tx1)] text-sm font-medium mb-1">Create a new classroom</p>
            <input required placeholder="Classroom name (e.g. Grade 10 Physics)" value={name}
              onChange={e => setName(e.target.value)} className={inputCls} />
            <div className="flex gap-2">
              <input placeholder="Subject (optional)" value={subject}
                onChange={e => setSubject(e.target.value)} className={inputCls} />
              <input placeholder="Grade / level (optional)" value={grade}
                onChange={e => setGrade(e.target.value)} className={inputCls} />
            </div>
            <div className="flex gap-2 pt-1">
              <button type="submit" disabled={creating || !name.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                           text-white text-sm rounded-xl transition-all disabled:opacity-40">
                {creating ? <Loader2 size={14} className="animate-spin" /> : 'Create'}
              </button>
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 text-[var(--tx6)] hover:text-[var(--tx2)] text-sm transition-colors">
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Classroom list */}
        {classrooms.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mx-auto mb-4">
              <Users size={28} className="text-[var(--tx7)]" />
            </div>
            <p className="text-[var(--tx3)] font-medium mb-1">No classrooms yet</p>
            <p className="text-[var(--tx7)] text-sm">Create one and share the join code with your students</p>
          </div>
        ) : (
          <div className="space-y-3">
            {classrooms.map(cls => (
              <div key={cls.id}
                className={`bg-[var(--surface)] border rounded-2xl p-5 transition-all ${
                  cls.is_active ? 'border-[var(--bd)]' : 'border-[var(--bd)] opacity-50'
                }`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="text-[var(--tx1)] font-semibold">{cls.name}</h3>
                      {!cls.is_active && (
                        <span className="text-xs px-2 py-0.5 bg-[var(--ov1)] text-[var(--tx7)] rounded-full">Archived</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 flex-wrap text-xs text-[var(--tx6)]">
                      {cls.subject && <span className="flex items-center gap-1"><BookOpen size={11} /> {cls.subject}</span>}
                      {cls.grade   && <span>{cls.grade}</span>}
                      <span className="flex items-center gap-1"><Users size={11} /> {cls.student_count} student{cls.student_count !== 1 ? 's' : ''}</span>
                    </div>
                  </div>

                  <button onClick={() => router.push(`/teacher/classrooms/${cls.id}`)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-[var(--tx6)] hover:text-[var(--tx1)]
                               hover:bg-[var(--ov3)] rounded-xl text-xs transition-all shrink-0">
                    View roster <ArrowRight size={12} />
                  </button>
                </div>

                {/* Join code */}
                <div className="mt-4 flex items-center gap-3 bg-[var(--ov1)] rounded-xl px-4 py-2.5">
                  <div className="flex-1">
                    <p className="text-[var(--tx8)] text-xs mb-0.5">Join code — share with students</p>
                    <p className="text-purple-400 font-mono text-lg font-bold tracking-[0.2em]">{cls.join_code}</p>
                  </div>
                  <button onClick={() => copyCode(cls.join_code, cls.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600/15 hover:bg-purple-600/25
                               text-purple-400 text-xs rounded-lg transition-all shrink-0">
                    {copiedId === cls.id ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
