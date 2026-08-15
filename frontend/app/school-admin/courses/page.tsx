'use client';
import { useEffect, useState, useCallback } from 'react';
import { BookOpen, Loader2, Plus, Trash2, Check, X } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SchoolCourse {
  school_course_id: string; course_id: string; course_name: string;
  subject: string | null; grade: string | null;
}
interface Course { id: string; name: string; subject: string | null; grade: string | null; }
interface Section { id: string; name: string; }

// sectionMap: section_id → Set of assigned school_course_ids
type SectionMap = Record<string, Set<string>>;

export default function CoursesPage() {
  const { token } = useSessionStore();
  const [schoolCourses, setSchoolCourses] = useState<SchoolCourse[]>([]);
  const [allCourses,    setAllCourses]    = useState<Course[]>([]);
  const [sections,      setSections]      = useState<Section[]>([]);
  const [sectionMap,    setSectionMap]    = useState<SectionMap>({});
  const [loading,       setLoading]       = useState(true);
  const [assignCourse,  setAssignCourse]  = useState('');
  const [saving,        setSaving]        = useState(false);
  // track in-flight toggles: `${secId}:${scId}`
  const [toggling,      setToggling]      = useState<Set<string>>(new Set());

  const authH = { Authorization: `Bearer ${token}` };

  const loadAll = useCallback(async () => {
    const [scRes, cRes, sRes, mapRes] = await Promise.all([
      fetch(`${API}/api/school/courses`,           { headers: authH }),
      fetch(`${API}/api/courses`,                   { headers: authH }),
      fetch(`${API}/api/school/sections`,           { headers: authH }),
      fetch(`${API}/api/school/section-courses-map`, { headers: authH }),
    ]);
    if (scRes.ok)  setSchoolCourses(await scRes.json());
    if (cRes.ok)   setAllCourses((await cRes.json()).courses ?? []);
    if (sRes.ok)   setSections(await sRes.json());
    if (mapRes.ok) {
      const raw: Record<string, string[]> = await mapRes.json();
      const built: SectionMap = {};
      for (const [sid, ids] of Object.entries(raw)) built[sid] = new Set(ids);
      setSectionMap(built);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => { if (token) loadAll(); }, [token]);

  // ── Add course to school ────────────────────────────────────────────────────
  async function assignToSchool() {
    if (!assignCourse) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/school/courses/assign`, {
        method: 'POST',
        headers: { ...authH, 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: assignCourse }),
      });
      if (res.ok) { setAssignCourse(''); await loadAll(); }
    } finally { setSaving(false); }
  }

  async function removeFromSchool(scId: string) {
    if (!confirm('Remove this course from the school? All classroom assignments will also be removed.')) return;
    await fetch(`${API}/api/school/courses/${scId}`, { method: 'DELETE', headers: authH });
    await loadAll();
  }

  // ── Toggle classroom assignment ─────────────────────────────────────────────
  async function toggleSection(secId: string, scId: string) {
    const key = `${secId}:${scId}`;
    if (toggling.has(key)) return;

    const assigned = sectionMap[secId]?.has(scId) ?? false;

    // Optimistic update
    setSectionMap(prev => {
      const next = { ...prev };
      const s = new Set(next[secId] ?? []);
      assigned ? s.delete(scId) : s.add(scId);
      next[secId] = s;
      return next;
    });
    setToggling(prev => new Set(prev).add(key));

    try {
      let ok = false;
      if (assigned) {
        const res = await fetch(`${API}/api/school/sections/${secId}/courses/${scId}`, {
          method: 'DELETE', headers: authH,
        });
        ok = res.ok;
      } else {
        const res = await fetch(`${API}/api/school/sections/${secId}/courses`, {
          method: 'POST',
          headers: { ...authH, 'Content-Type': 'application/json' },
          body: JSON.stringify({ school_course_id: scId }),
        });
        ok = res.ok;
      }
      if (!ok) {
        // Roll back on failure
        setSectionMap(prev => {
          const next = { ...prev };
          const s = new Set(next[secId] ?? []);
          assigned ? s.add(scId) : s.delete(scId);
          next[secId] = s;
          return next;
        });
      }
    } finally {
      setToggling(prev => { const s = new Set(prev); s.delete(key); return s; });
    }
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

      {/* Add course to school */}
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
          <button
            onClick={assignToSchool}
            disabled={saving || !assignCourse}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl disabled:opacity-40"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : 'Add'}
          </button>
        </div>
        {unassignedCourses.length === 0 && allCourses.length > 0 && (
          <p className="text-xs text-[var(--tx7)] mt-2">All courses are already added to the school.</p>
        )}
      </div>

      {/* School course list */}
      {schoolCourses.length === 0 ? (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-8 text-center">
          <BookOpen size={32} className="text-[var(--tx7)] mx-auto mb-3" />
          <p className="text-[var(--tx5)] text-sm">No courses added to school yet.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {schoolCourses.map(sc => (
            <div
              key={sc.school_course_id}
              className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden"
            >
              {/* Course header */}
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-[var(--tx1)] font-medium text-sm">{sc.course_name}</p>
                  {(sc.subject || sc.grade) && (
                    <p className="text-[var(--tx7)] text-xs">
                      {[sc.subject, sc.grade ? `Grade ${sc.grade}` : null].filter(Boolean).join(' · ')}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => removeFromSchool(sc.school_course_id)}
                  className="p-2 text-[var(--tx7)] hover:text-red-400 rounded-lg hover:bg-[var(--ov2)] transition-colors"
                  title="Remove from school"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              {/* Classroom chips */}
              <div className="border-t border-[var(--bd)] px-5 py-3">
                {sections.length === 0 ? (
                  <p className="text-xs text-[var(--tx7)]">No classrooms yet.</p>
                ) : (
                  <>
                    <p className="text-xs text-[var(--tx6)] mb-2">Assign to classrooms:</p>
                    <div className="flex flex-wrap gap-2">
                      {sections.map(sec => {
                        const assigned = sectionMap[sec.id]?.has(sc.school_course_id) ?? false;
                        const key = `${sec.id}:${sc.school_course_id}`;
                        const busy = toggling.has(key);
                        return (
                          <button
                            key={sec.id}
                            onClick={() => toggleSection(sec.id, sc.school_course_id)}
                            disabled={busy}
                            title={assigned ? `Remove from ${sec.name}` : `Assign to ${sec.name}`}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full border transition-all ${
                              busy
                                ? 'opacity-50 cursor-wait border-[var(--bd)] text-[var(--tx6)]'
                                : assigned
                                  ? 'bg-purple-600/20 border-purple-500/40 text-purple-300 hover:bg-red-500/10 hover:border-red-500/30 hover:text-red-400'
                                  : 'bg-[var(--ov2)] border-[var(--bd)] text-[var(--tx5)] hover:border-purple-500/40 hover:text-purple-300'
                            }`}
                          >
                            {busy
                              ? <Loader2 size={10} className="animate-spin" />
                              : assigned
                                ? <Check size={10} />
                                : <Plus size={10} />
                            }
                            {sec.name}
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
