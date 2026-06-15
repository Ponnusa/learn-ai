'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, BookOpen, ArrowRight, Loader2, FileText, Layers } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Course {
  id: string;
  name: string;
  description?: string;
  subject?: string;
  grade?: string;
  status: string;
  unit_count: number;
  concept_count: number;
  created_at: string;
}

export default function TeacherCoursesPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();

  const [courses,   setCourses]  = useState<Course[]>([]);
  const [loading,   setLoading]  = useState(true);
  const [showForm,  setShowForm] = useState(false);
  const [creating,  setCreating] = useState(false);
  const [name,      setName]     = useState('');
  const [subject,   setSubject]  = useState('');
  const [grade,     setGrade]    = useState('');
  const [desc,      setDesc]     = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/mine`, { headers });
      if (res.ok) setCourses(await res.json());
    } finally { setLoading(false); }
  }

  async function createCourse(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses`, {
        method: 'POST', headers,
        body: JSON.stringify({ name: name.trim(), description: desc || undefined, subject: subject || undefined, grade: grade || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      router.push(`/teacher/courses/${data.id}`);
    } catch (err: any) {
      alert(err.message);
    } finally { setCreating(false); }
  }

  const inputCls = `w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-2.5
                    text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors`;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={28} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-[var(--tx1)] text-2xl font-bold">Course Builder</h1>
          <p className="text-[var(--tx6)] text-sm mt-1">{courses.length} course{courses.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setShowForm(s => !s)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                     text-white text-sm font-medium rounded-xl transition-all"
        >
          <Plus size={16} /> New course
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={createCourse}
          className="bg-[var(--surface)] border border-purple-500/30 rounded-2xl p-5 mb-6 space-y-3">
          <p className="text-[var(--tx1)] text-sm font-medium">Create a new course</p>
          <input required placeholder="Course name (e.g. Physics — Grade 11)" value={name}
            onChange={e => setName(e.target.value)} className={inputCls} />
          <textarea placeholder="Description (optional)" value={desc} rows={2}
            onChange={e => setDesc(e.target.value)} className={`${inputCls} resize-none`} />
          <div className="flex gap-2">
            <input placeholder="Subject" value={subject} onChange={e => setSubject(e.target.value)} className={inputCls} />
            <input placeholder="Grade / level" value={grade} onChange={e => setGrade(e.target.value)} className={inputCls} />
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={creating || !name.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                         text-white text-sm rounded-xl transition-all disabled:opacity-40">
              {creating ? <Loader2 size={14} className="animate-spin" /> : 'Create & open'}
            </button>
            <button type="button" onClick={() => setShowForm(false)}
              className="px-4 py-2 text-[var(--tx6)] hover:text-[var(--tx2)] text-sm transition-colors">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Course list */}
      {courses.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mx-auto mb-4">
            <BookOpen size={28} className="text-[var(--tx7)]" />
          </div>
          <p className="text-[var(--tx3)] font-medium mb-1">No courses yet</p>
          <p className="text-[var(--tx7)] text-sm">Create one manually or import from a syllabus PDF</p>
        </div>
      ) : (
        <div className="space-y-3">
          {courses.map(c => (
            <button key={c.id} onClick={() => router.push(`/teacher/courses/${c.id}`)}
              className="w-full text-left bg-[var(--surface)] border border-[var(--bd)]
                         hover:border-purple-500/30 rounded-2xl p-5 transition-all group">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h3 className="text-[var(--tx1)] font-semibold">{c.name}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      c.status === 'published'
                        ? 'bg-green-500/15 text-green-400'
                        : 'bg-[var(--ov1)] text-[var(--tx7)]'
                    }`}>{c.status}</span>
                  </div>
                  {c.description && <p className="text-[var(--tx6)] text-sm mb-2 line-clamp-1">{c.description}</p>}
                  <div className="flex items-center gap-4 text-xs text-[var(--tx7)]">
                    {c.subject && <span>{c.subject}</span>}
                    {c.grade   && <span>{c.grade}</span>}
                    <span className="flex items-center gap-1"><Layers size={10} /> {c.unit_count} units</span>
                    <span className="flex items-center gap-1"><FileText size={10} /> {c.concept_count} concepts</span>
                  </div>
                </div>
                <ArrowRight size={16} className="text-[var(--tx8)] group-hover:text-purple-400 transition-colors shrink-0 mt-1" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
