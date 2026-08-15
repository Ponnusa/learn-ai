'use client';
import { useEffect, useState } from 'react';
import { BookOpen, Loader2, Plus, Trash2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SchoolCourse {
  school_course_id: string; course_id: string; course_name: string;
  subject: string | null; grade: string | null;
}
interface Course { id: string; name: string; subject: string | null; grade: string | null; }
interface Section { id: string; name: string; }
interface SectionCourse { school_course_id: string; course_name: string; }

export default function CoursesPage() {
  const { token } = useSessionStore();
  const [schoolCourses, setSchoolCourses] = useState<SchoolCourse[]>([]);
  const [allCourses,    setAllCourses]    = useState<Course[]>([]);
  const [sections,      setSections]      = useState<Section[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [assignCourse,  setAssignCourse]  = useState('');
  const [saving,        setSaving]        = useState(false);
  const [sectionCourses, setSectionCourses] = useState<Record<string, SectionCourse[]>>({});
  const [assigning,     setAssigning]     = useState<{ secId: string; scId: string } | null>(null);

  async function load() {
    const [scRes, cRes, sRes] = await Promise.all([
      fetch(`${API}/api/school/courses`,  { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/courses`,          { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/school/sections`, { headers: { Authorization: `Bearer ${token}` } }),
    ]);
    if (scRes.ok) setSchoolCourses(await scRes.json());
    if (cRes.ok)  setAllCourses((await cRes.json()).courses ?? []);
    if (sRes.ok)  setSections(await sRes.json());
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

  async function assignToSchool() {
    if (!assignCourse) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/school/courses/assign`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: assignCourse }),
      });
      if (res.ok) { setAssignCourse(''); await load(); }
    } finally { setSaving(false); }
  }

  async function removeFromSchool(scId: string) {
    if (!confirm('Remove this course from the school? All section assignments will also be removed.')) return;
    await fetch(`${API}/api/school/courses/${scId}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    });
    await load();
  }

  async function loadSectionCourses(secId: string) {
    const res = await fetch(`${API}/api/school/sections/${secId}/courses`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setSectionCourses(p => ({ ...p, [secId]: data }));
    }
  }

  async function assignToSection(secId: string, scId: string) {
    setAssigning({ secId, scId });
    try {
      await fetch(`${API}/api/school/sections/${secId}/courses`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ school_course_id: scId }),
      });
      await loadSectionCourses(secId);
    } finally { setAssigning(null); }
  }

  async function removeFromSection(secId: string, scId: string) {
    await fetch(`${API}/api/school/sections/${secId}/courses/${scId}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    });
    await loadSectionCourses(secId);
  }

  const unassignedCourses = allCourses.filter(c => !schoolCourses.some(sc => sc.course_id === c.id));

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-[var(--tx1)] text-xl font-bold mb-6">Courses</h1>

      {/* Assign to school */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
        <p className="text-[var(--tx3)] text-sm font-medium mb-3 flex items-center gap-2">
          <Plus size={15} className="text-purple-400" /> Add Course to School
        </p>
        <div className="flex gap-2">
          <select
            value={assignCourse}
            onChange={e => setAssignCourse(e.target.value)}
            className="flex-1 bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                       text-[var(--tx1)] outline-none focus:border-purple-500/60"
          >
            <option value="">— Select a course —</option>
            {unassignedCourses.map(c => (
              <option key={c.id} value={c.id}>{c.name}{c.subject ? ` (${c.subject})` : ''}</option>
            ))}
          </select>
          <button onClick={assignToSchool} disabled={saving || !assignCourse}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl disabled:opacity-40">
            {saving ? <Loader2 size={14} className="animate-spin" /> : 'Add'}
          </button>
        </div>
        {unassignedCourses.length === 0 && allCourses.length > 0 && (
          <p className="text-xs text-[var(--tx7)] mt-2">All courses are already added to the school.</p>
        )}
      </div>

      {/* School courses */}
      {schoolCourses.length === 0 ? (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 text-center">
          <BookOpen size={32} className="text-[var(--tx7)] mx-auto mb-3" />
          <p className="text-[var(--tx5)] text-sm">No courses added to school yet.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {schoolCourses.map(sc => (
            <div key={sc.school_course_id}
              className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">
              {/* Course header */}
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-[var(--tx1)] font-medium text-sm">{sc.course_name}</p>
                  <p className="text-[var(--tx7)] text-xs">
                    {[sc.subject, sc.grade ? `Grade ${sc.grade}` : null].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => removeFromSchool(sc.school_course_id)}
                    className="p-2 text-[var(--tx7)] hover:text-red-400 rounded-lg hover:bg-[var(--ov2)] transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Assign to sections */}
              <div className="border-t border-[var(--bd)] px-5 py-3">
                <p className="text-xs text-[var(--tx6)] mb-2">Assign to classrooms:</p>
                <div className="flex flex-wrap gap-2">
                  {sections.map(sec => {
                    const secCourses = sectionCourses[sec.id] ?? [];
                    const already = secCourses.some(c => c.school_course_id === sc.school_course_id);
                    const busy = assigning?.secId === sec.id && assigning?.scId === sc.school_course_id;
                    return (
                      <button
                        key={sec.id}
                        onClick={() => already
                          ? removeFromSection(sec.id, sc.school_course_id)
                          : assignToSection(sec.id, sc.school_course_id)
                        }
                        onMouseEnter={() => { if (!sectionCourses[sec.id]) loadSectionCourses(sec.id); }}
                        disabled={busy}
                        className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                          already
                            ? 'bg-purple-600/20 border-purple-500/40 text-purple-300 hover:bg-red-500/10 hover:border-red-500/30 hover:text-red-400'
                            : 'bg-[var(--ov2)] border-[var(--bd)] text-[var(--tx5)] hover:border-purple-500/40 hover:text-purple-300'
                        }`}
                      >
                        {busy ? '...' : sec.name}
                        {already && ' ✓'}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
