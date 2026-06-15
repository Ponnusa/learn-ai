'use client';
import { useEffect, useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Plus, Trash2, ChevronDown, ChevronRight,
  Upload, Loader2, Check, BookOpen, FileText, Users,
  CheckCircle, Globe,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Concept { id: string; title: string; description?: string; study_set_id?: string; ss_status?: string; position: number; }
interface Unit    { id: string; title: string; description?: string; position: number; concepts: Concept[]; }
interface Classroom { id: string; name: string; }
interface Course  {
  id: string; name: string; description?: string;
  subject?: string; grade?: string; status: string;
  units: Unit[]; classrooms: Classroom[];
}

// Import preview shape
interface PreviewUnit { title: string; description?: string; concepts: { title: string; description?: string }[]; }

export default function CourseDetailPage() {
  const router  = useRouter();
  const params  = useParams();
  const courseId = params.id as string;
  const { user, token } = useSessionStore();

  const [course,      setCourse]      = useState<Course | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [expanded,    setExpanded]    = useState<Set<string>>(new Set());
  const [addingUnit,  setAddingUnit]  = useState(false);
  const [unitTitle,   setUnitTitle]   = useState('');
  const [addingConcept, setAddingConcept] = useState<string | null>(null);
  const [conceptTitle, setConceptTitle]  = useState('');

  // Syllabus import
  const fileRef    = useRef<HTMLInputElement>(null);
  const [importing,  setImporting]    = useState(false);
  const [preview,    setPreview]      = useState<PreviewUnit[] | null>(null);
  const [confirming, setConfirming]   = useState(false);
  const [importMsg,  setImportMsg]    = useState('');

  // Assign to classroom
  const [myClassrooms, setMyClassrooms] = useState<Classroom[]>([]);
  const [assigning,    setAssigning]    = useState(false);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
    loadClassrooms();
  }, [user, courseId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}`, { headers });
      if (!res.ok) { router.replace('/teacher/courses'); return; }
      const data = await res.json();
      setCourse(data);
      setExpanded(new Set(data.units.map((u: Unit) => u.id)));
    } finally { setLoading(false); }
  }

  async function loadClassrooms() {
    const res = await fetch(`${API_BASE}/api/classrooms/teaching`, { headers });
    if (res.ok) setMyClassrooms(await res.json());
  }

  // ── Units ──────────────────────────────────────────────────────────────────

  async function addUnit(e: React.FormEvent) {
    e.preventDefault();
    if (!unitTitle.trim()) return;
    const res = await fetch(`${API_BASE}/api/courses/${courseId}/units`, {
      method: 'POST', headers,
      body: JSON.stringify({ title: unitTitle.trim() }),
    });
    const unit = await res.json();
    setCourse(prev => prev ? { ...prev, units: [...prev.units, { ...unit }] } : prev);
    setExpanded(prev => new Set([...prev, unit.id]));
    setUnitTitle(''); setAddingUnit(false);
  }

  async function deleteUnit(unitId: string) {
    if (!confirm('Delete this unit and all its concepts?')) return;
    await fetch(`${API_BASE}/api/courses/units/${unitId}`, { method: 'DELETE', headers });
    setCourse(prev => prev ? { ...prev, units: prev.units.filter(u => u.id !== unitId) } : prev);
  }

  // ── Concepts ───────────────────────────────────────────────────────────────

  async function addConcept(unitId: string, e: React.FormEvent) {
    e.preventDefault();
    if (!conceptTitle.trim()) return;
    const res = await fetch(`${API_BASE}/api/courses/units/${unitId}/concepts`, {
      method: 'POST', headers,
      body: JSON.stringify({ title: conceptTitle.trim() }),
    });
    const concept = await res.json();
    setCourse(prev => prev ? {
      ...prev,
      units: prev.units.map(u => u.id === unitId ? { ...u, concepts: [...u.concepts, concept] } : u),
    } : prev);
    setConceptTitle(''); setAddingConcept(null);
  }

  async function deleteConcept(unitId: string, conceptId: string) {
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}`, { method: 'DELETE', headers });
    setCourse(prev => prev ? {
      ...prev,
      units: prev.units.map(u => u.id === unitId
        ? { ...u, concepts: u.concepts.filter(c => c.id !== conceptId) }
        : u),
    } : prev);
  }

  // ── Syllabus import ────────────────────────────────────────────────────────

  async function handleFileUpload(file: File) {
    setImporting(true); setPreview(null); setImportMsg('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/import-syllabus`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Import failed');
      setPreview(data.units);
      setImportMsg(`Found ${data.unit_count} units and ${data.concept_count} concepts from ${data.page_count} pages`);
    } catch (err: any) {
      alert(err.message);
    } finally { setImporting(false); }
  }

  async function confirmImport() {
    if (!preview) return;
    setConfirming(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/confirm-import`, {
        method: 'POST', headers,
        body: JSON.stringify({ units: preview }),
      });
      if (!res.ok) throw new Error('Failed to save');
      setPreview(null); setImportMsg('');
      load();
    } catch (err: any) {
      alert(err.message);
    } finally { setConfirming(false); }
  }

  // ── Assign to classroom ────────────────────────────────────────────────────

  async function toggleAssign(classroomId: string, assigned: boolean) {
    setAssigning(true);
    try {
      if (assigned) {
        await fetch(`${API_BASE}/api/courses/${courseId}/assign/${classroomId}`, {
          method: 'DELETE', headers,
        });
        setCourse(prev => prev ? {
          ...prev, classrooms: prev.classrooms.filter(c => c.id !== classroomId),
        } : prev);
      } else {
        await fetch(`${API_BASE}/api/courses/${courseId}/assign`, {
          method: 'POST', headers,
          body: JSON.stringify({ classroom_id: classroomId }),
        });
        const cls = myClassrooms.find(c => c.id === classroomId);
        if (cls) setCourse(prev => prev ? { ...prev, classrooms: [...prev.classrooms, cls] } : prev);
      }
    } finally { setAssigning(false); }
  }

  async function publish() {
    await fetch(`${API_BASE}/api/courses/${courseId}`, {
      method: 'PATCH', headers,
      body: JSON.stringify({ status: course?.status === 'published' ? 'draft' : 'published' }),
    });
    setCourse(prev => prev ? {
      ...prev, status: prev.status === 'published' ? 'draft' : 'published',
    } : prev);
  }

  const inputCls = `bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2
                    text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors`;

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!course) return null;

  const assignedIds = new Set(course.classrooms.map(c => c.id));

  return (
    <div className="p-6 max-w-3xl mx-auto">

      {/* Back */}
      <button onClick={() => router.push('/teacher/courses')}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> Back to courses
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-[var(--tx1)] text-2xl font-bold">{course.name}</h1>
          <div className="flex items-center gap-3 mt-1 text-xs text-[var(--tx6)]">
            {course.subject && <span>{course.subject}</span>}
            {course.grade   && <span>{course.grade}</span>}
            <span className={`px-2 py-0.5 rounded-full ${
              course.status === 'published' ? 'bg-green-500/15 text-green-400' : 'bg-[var(--ov1)] text-[var(--tx7)]'
            }`}>{course.status}</span>
          </div>
        </div>
        <button onClick={publish}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border transition-all ${
            course.status === 'published'
              ? 'border-green-500/30 text-green-400 hover:bg-green-500/10'
              : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400'
          }`}>
          {course.status === 'published' ? <><CheckCircle size={14} /> Published</> : <><Globe size={14} /> Publish</>}
        </button>
      </div>

      {/* Syllabus import */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-[var(--tx2)] text-sm font-medium">Import from syllabus PDF</p>
            <p className="text-[var(--tx7)] text-xs mt-0.5">AI will extract units and concepts automatically</p>
          </div>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={importing}
            className="flex items-center gap-2 px-3 py-2 bg-purple-600/15 hover:bg-purple-600/25
                       text-purple-400 text-sm rounded-xl transition-all disabled:opacity-40"
          >
            {importing ? <Loader2 size={14} className="animate-spin" /> : <><Upload size={14} /> Upload PDF</>}
          </button>
          <input ref={fileRef} type="file" accept=".pdf" className="hidden"
            onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])} />
        </div>

        {importMsg && !preview && <p className="text-[var(--tx6)] text-xs">{importMsg}</p>}

        {/* Import preview */}
        {preview && (
          <div className="mt-4 border-t border-[var(--bd)] pt-4">
            <p className="text-[var(--tx2)] text-sm font-medium mb-1">{importMsg}</p>
            <p className="text-[var(--tx7)] text-xs mb-3">Review the extracted structure below, then confirm to save.</p>
            <div className="space-y-2">
              {preview.map((unit, ui) => (
                <div key={ui} className="bg-[var(--ov1)] rounded-xl p-3">
                  <p className="text-[var(--tx2)] text-sm font-medium">{ui + 1}. {unit.title}</p>
                  <div className="mt-1.5 space-y-1 pl-3">
                    {unit.concepts.map((c, ci) => (
                      <p key={ci} className="text-[var(--tx6)] text-xs">· {c.title}</p>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={confirmImport} disabled={confirming}
                className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500
                           text-white text-sm rounded-xl transition-all disabled:opacity-40">
                {confirming ? <Loader2 size={14} className="animate-spin" /> : <><Check size={14} /> Confirm &amp; save</>}
              </button>
              <button onClick={() => { setPreview(null); setImportMsg(''); }}
                className="px-4 py-2 text-[var(--tx6)] hover:text-[var(--tx2)] text-sm transition-colors">
                Discard
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Units + concepts */}
      <div className="space-y-3 mb-8">
        {course.units.map((unit, ui) => (
          <div key={unit.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">
            {/* Unit header */}
            <div className="flex items-center gap-3 px-5 py-4">
              <button onClick={() => setExpanded(prev => {
                const n = new Set(prev);
                n.has(unit.id) ? n.delete(unit.id) : n.add(unit.id);
                return n;
              })} className="text-[var(--tx6)] hover:text-[var(--tx2)] transition-colors">
                {expanded.has(unit.id) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>
              <div className="flex-1">
                <p className="text-[var(--tx1)] font-semibold text-sm">
                  Unit {ui + 1}: {unit.title}
                </p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">{unit.concepts.length} concept{unit.concepts.length !== 1 ? 's' : ''}</p>
              </div>
              <button onClick={() => deleteUnit(unit.id)}
                className="text-[var(--tx8)] hover:text-red-400 transition-colors p-1">
                <Trash2 size={14} />
              </button>
            </div>

            {/* Concepts */}
            {expanded.has(unit.id) && (
              <div className="border-t border-[var(--bd)] px-5 py-3 space-y-1.5">
                {unit.concepts.map((c, ci) => (
                  <div key={c.id} className="flex items-center gap-3 group py-1">
                    <span className="text-[var(--tx8)] text-xs w-5 text-right shrink-0">{ci + 1}.</span>
                    <button
                      onClick={() => router.push(`/teacher/courses/${courseId}/concepts/${c.id}`)}
                      className="flex-1 min-w-0 text-left hover:text-purple-400 transition-colors">
                      <p className="text-[var(--tx2)] text-sm truncate group-hover:text-purple-400 transition-colors">{c.title}</p>
                      {c.ss_status === 'ready'
                        ? <span className="text-xs text-green-400 flex items-center gap-1"><BookOpen size={9} /> Study set ready</span>
                        : <span className="text-xs text-[var(--tx8)]">Click to add explanation &amp; materials</span>
                      }
                    </button>
                    <button onClick={() => deleteConcept(unit.id, c.id)}
                      className="opacity-0 group-hover:opacity-100 text-[var(--tx8)] hover:text-red-400
                                 transition-all p-1 shrink-0">
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}

                {/* Add concept inline */}
                {addingConcept === unit.id ? (
                  <form onSubmit={e => addConcept(unit.id, e)} className="flex gap-2 mt-2">
                    <input autoFocus placeholder="Concept title" value={conceptTitle}
                      onChange={e => setConceptTitle(e.target.value)}
                      className={`${inputCls} flex-1`} />
                    <button type="submit"
                      className="px-3 py-1.5 bg-purple-600 text-white text-xs rounded-lg">Add</button>
                    <button type="button" onClick={() => { setAddingConcept(null); setConceptTitle(''); }}
                      className="px-3 py-1.5 text-[var(--tx7)] text-xs rounded-lg">Cancel</button>
                  </form>
                ) : (
                  <button onClick={() => { setAddingConcept(unit.id); setConceptTitle(''); }}
                    className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-purple-400 text-xs
                               transition-colors mt-1 py-1">
                    <Plus size={12} /> Add concept
                  </button>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Add unit */}
        {addingUnit ? (
          <form onSubmit={addUnit}
            className="bg-[var(--surface)] border border-purple-500/30 rounded-2xl p-4 flex gap-2">
            <input autoFocus placeholder="Unit title" value={unitTitle}
              onChange={e => setUnitTitle(e.target.value)}
              className={`${inputCls} flex-1`} />
            <button type="submit"
              className="px-3 py-2 bg-purple-600 text-white text-sm rounded-xl">Add</button>
            <button type="button" onClick={() => { setAddingUnit(false); setUnitTitle(''); }}
              className="px-3 py-2 text-[var(--tx7)] text-sm rounded-xl">Cancel</button>
          </form>
        ) : (
          <button onClick={() => setAddingUnit(true)}
            className="w-full flex items-center justify-center gap-2 py-3 border border-dashed
                       border-[var(--bd)] hover:border-purple-500/40 rounded-2xl text-[var(--tx7)]
                       hover:text-purple-400 text-sm transition-all">
            <Plus size={15} /> Add unit
          </button>
        )}
      </div>

      {/* Assign to classrooms */}
      {myClassrooms.length > 0 && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Users size={16} className="text-[var(--tx6)]" />
            <p className="text-[var(--tx2)] text-sm font-medium">Assign to classrooms</p>
          </div>
          <div className="space-y-2">
            {myClassrooms.map(cls => {
              const assigned = assignedIds.has(cls.id);
              return (
                <div key={cls.id} className="flex items-center justify-between p-3 bg-[var(--ov1)] rounded-xl">
                  <p className="text-[var(--tx2)] text-sm">{cls.name}</p>
                  <button
                    onClick={() => toggleAssign(cls.id, assigned)}
                    disabled={assigning}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-all ${
                      assigned
                        ? 'bg-green-500/15 text-green-400 hover:bg-red-500/15 hover:text-red-400'
                        : 'bg-[var(--ov3)] text-[var(--tx6)] hover:bg-purple-500/15 hover:text-purple-400'
                    }`}
                  >
                    {assigned ? <><Check size={11} /> Assigned</> : <><Plus size={11} /> Assign</>}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
