'use client';
import { useEffect, useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Plus, Trash2, ChevronDown, ChevronRight,
  Upload, Loader2, Check, BookOpen, Users,
  CheckCircle, Globe, Zap, Circle, Crop, Sparkles, ListChecks, Wand2,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { PDFViewerModal } from '@/components/chat/PDFViewerModal';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type PipelineStatus = 'draft' | 'summarizing' | 'ready' | 'approved' | 'failed';
interface Concept {
  id: string; title: string; description?: string; study_set_id?: string; ss_status?: string;
  pipeline_status?: PipelineStatus; position: number; source?: 'ai' | 'manual';
}
interface Unit    { id: string; title: string; description?: string; position: number; chapter_ref?: string | null; concepts: Concept[]; }
interface Classroom { id: string; name: string; }
interface Course  {
  id: string; name: string; description?: string;
  subject?: string; grade?: string; status: string;
  units: Unit[]; classrooms: Classroom[];
}

export default function CourseDetailPage() {
  const router  = useRouter();
  const params  = useParams();
  const courseId = params.id as string;
  const { user, token } = useSessionStore();

  const { t, tF } = useTranslation();
  const [course,      setCourse]      = useState<Course | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [expanded,    setExpanded]    = useState<Set<string>>(new Set());
  const [addingUnit,  setAddingUnit]  = useState(false);
  const [unitTitle,   setUnitTitle]   = useState('');
  const [addingConcept, setAddingConcept] = useState<string | null>(null);
  const [conceptTitle, setConceptTitle]  = useState('');

  // Chapter upload (full AI pipeline)
  const chapterRef = useRef<HTMLInputElement>(null);
  const [uploading,     setUploading]     = useState(false);
  const [pipelineMsg,   setPipelineMsg]   = useState('');
  const [isProcessing,  setIsProcessing]  = useState(false);
  const [processedCount, setProcessedCount] = useState(0);
  const [totalCount,    setTotalCount]    = useState(0);
  const [detecting,     setDetecting]     = useState(false);

  // Multi-chapter textbook detection — review/edit panel before splitting
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [detectedChapters, setDetectedChapters] = useState<
    { title: string; start_page: number; end_page: number; low_confidence?: boolean }[] | null
  >(null);
  const [splitting, setSplitting] = useState(false);

  // Assign to classroom
  const [myClassrooms, setMyClassrooms] = useState<Classroom[]>([]);
  const [assigning,    setAssigning]    = useState(false);

  // Manual concept creation — crop a region of the chapter PDF as an image
  const [cropTarget, setCropTarget] = useState<{ unitId: string; chapterRefId: string; file: File } | null>(null);
  const [suggestingFor, setSuggestingFor] = useState<string | null>(null);
  const [coverageBusy,   setCoverageBusy]   = useState<string | null>(null);
  const [coverageResult, setCoverageResult] = useState<{ chapterId: string; summary: string } | null>(null);

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

  // ── Pipeline polling ───────────────────────────────────────────────────────

  useEffect(() => {
    if (!isProcessing) return;
    const iv = setInterval(async () => {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/pipeline`, { headers });
      if (!res.ok) return;
      const data = await res.json();
      const done = (data.counts?.approved ?? 0) + (data.counts?.ready ?? 0) + (data.counts?.failed ?? 0);
      setProcessedCount(done);
      if (!data.is_processing) {
        setIsProcessing(false);
        setPipelineMsg('');
        load();
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [isProcessing, courseId]);

  // ── Chapter upload ──────────────────────────────────────────────────────────

  async function handleChapterUpload(file: File) {
    setUploading(true); setPipelineMsg('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/chapters`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      // No auto-extraction anymore — the chapter lands as an empty unit. The
      // teacher either crops concepts from the PDF or clicks "Suggest concepts".
      await load();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(false);
      if (chapterRef.current) chapterRef.current.value = '';
    }
  }

  async function suggestConcepts(chapterRefId: string) {
    setSuggestingFor(chapterRefId); setPipelineMsg('');
    try {
      const res = await fetch(`${API_BASE}/api/courses/chapters/${chapterRefId}/suggest-concepts`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Suggest concepts failed');
      setTotalCount(data.concept_count);
      setProcessedCount(0);
      setIsProcessing(true);
      setPipelineMsg(`Generating content for ${data.concept_count} concepts…`);
      load();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSuggestingFor(null);
    }
  }

  async function checkCoverage(chapterRefId: string) {
    setCoverageBusy(chapterRefId);
    setCoverageResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/courses/chapters/${chapterRefId}/coverage-check`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Coverage check failed');
      setCoverageResult({ chapterId: chapterRefId, summary: data.coverage_summary });
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCoverageBusy(null);
    }
  }

  async function createConceptFromRegion(unitId: string, chapterRefId: string, imageDataUrl: string) {
    try {
      const res = await fetch(`${API_BASE}/api/courses/chapters/${chapterRefId}/concepts/from-region`, {
        method: 'POST', headers,
        body: JSON.stringify({ unit_id: unitId, image_data_url: imageDataUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not create concept from this selection');
      setCropTarget(null);
      router.push(`/teacher/courses/${courseId}/concepts/${data.concept_id}`);
    } catch (err: any) {
      alert(err.message);
    }
  }

  async function openCropModal(unitId: string, chapterRefId: string) {
    const res = await fetch(`${API_BASE}/api/courses/chapters/${chapterRefId}/pdf`, { headers });
    if (!res.ok) { alert('Could not load the chapter PDF'); return; }
    const blob = await res.blob();
    const file = new File([blob], 'chapter.pdf', { type: 'application/pdf' });
    setCropTarget({ unitId, chapterRefId, file });
  }

  // First step on file pick: check whether this looks like a whole textbook
  // with multiple chapters, before committing to the single-chapter upload.
  async function handleFileSelected(file: File) {
    setDetecting(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/chapters/detect-toc`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json();
      if (res.ok && data.detected) {
        setPendingFile(file);
        setDetectedChapters(data.chapters);
      } else {
        await handleChapterUpload(file);
      }
    } catch {
      // Detection failing shouldn't block the upload — fall back to today's flow.
      await handleChapterUpload(file);
    } finally {
      setDetecting(false);
    }
  }

  function updateDetectedChapter(i: number, field: 'start_page' | 'end_page' | 'title', value: string) {
    setDetectedChapters(prev => prev?.map((c, idx) => idx === i
      ? { ...c, [field]: field === 'title' ? value : Number(value) }
      : c) ?? null);
  }

  function cancelDetectedSplit() {
    setPendingFile(null);
    setDetectedChapters(null);
    if (chapterRef.current) chapterRef.current.value = '';
  }

  async function confirmSplit() {
    if (!pendingFile || !detectedChapters) return;
    setSplitting(true); setPipelineMsg('');
    try {
      const fd = new FormData();
      fd.append('file', pendingFile);
      fd.append('chapters', JSON.stringify(detectedChapters.map(({ title, start_page, end_page }) => ({ title, start_page, end_page }))));
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/chapters/bulk-split`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Split failed');
      setTotalCount(data.concept_count);
      setProcessedCount(0);
      setIsProcessing(true);
      setPipelineMsg(`Created ${data.chapters.length} chapters — generating content for ${data.concept_count} concepts…`);
      load();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSplitting(false);
      cancelDetectedSplit();
    }
  }

  async function useAsOneChapter() {
    if (!pendingFile) return;
    const file = pendingFile;
    cancelDetectedSplit();
    await handleChapterUpload(file);
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
        <ArrowLeft size={15} /> {t.teacher.backToCourses}
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
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => router.push(`/teacher/courses/${courseId}/progress`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all">
            <Users size={14} /> {t.teacher.progressBtn}
          </button>
          <button onClick={publish}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border transition-all ${
              course.status === 'published'
                ? 'border-green-500/30 text-green-400 hover:bg-green-500/10'
                : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400'
            }`}>
            {course.status === 'published' ? <><CheckCircle size={14} /> {t.teacher.published}</> : <><Globe size={14} /> {t.teacher.publishBtn}</>}
          </button>
        </div>
      </div>

      {/* Pipeline status banner */}
      {isProcessing && (
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-2xl p-4 mb-4 flex items-center gap-3">
          <Loader2 size={16} className="text-purple-400 animate-spin shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-purple-300 text-sm font-medium">{t.teacher.aiGenerating}</p>
            <p className="text-purple-400/70 text-xs mt-0.5 truncate">{pipelineMsg}</p>
          </div>
          {totalCount > 0 && (
            <span className="text-purple-300 text-xs font-mono shrink-0">
              {processedCount}/{totalCount}
            </span>
          )}
        </div>
      )}

      {/* Chapter upload — AI pipeline */}
      <div className="bg-[var(--surface)] border border-purple-500/20 rounded-2xl p-5 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[var(--tx1)] text-sm font-semibold flex items-center gap-1.5">
              <Zap size={14} className="text-purple-400" /> {t.teacher.uploadChapterTitle}
            </p>
            <p className="text-[var(--tx7)] text-xs mt-1">
              {t.teacher.uploadChapterDesc}
            </p>
          </div>
          <button onClick={() => chapterRef.current?.click()} disabled={uploading || detecting || isProcessing}
            className="shrink-0 flex items-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-500
                       text-white text-sm rounded-xl transition-all disabled:opacity-40">
            {uploading || detecting ? <Loader2 size={14} className="animate-spin" /> : <><Upload size={14} /> {t.teacher.uploadChapterBtn}</>}
          </button>
          <input ref={chapterRef} type="file" accept=".pdf" className="hidden"
            onChange={e => e.target.files?.[0] && handleFileSelected(e.target.files[0])} />
        </div>
      </div>

      {/* Detected multi-chapter textbook — review/edit before splitting */}
      {detectedChapters && (
        <div className="bg-[var(--surface)] border border-purple-500/30 rounded-2xl p-5 mb-6">
          <p className="text-[var(--tx1)] text-sm font-semibold mb-1">
            {tF(t.teacher.detectedChapters, { n: detectedChapters.length })}
          </p>
          <p className="text-[var(--tx7)] text-xs mb-4">
            {t.teacher.reviewRanges}
          </p>
          <div className="space-y-2 mb-4">
            {detectedChapters.map((c, i) => (
              <div key={i} className="flex items-center gap-2">
                <input value={c.title} onChange={e => updateDetectedChapter(i, 'title', e.target.value)}
                  className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-2.5 py-1.5 text-sm text-[var(--tx1)]" />
                <span className="text-[var(--tx7)] text-xs">p.</span>
                <input type="number" value={c.start_page} onChange={e => updateDetectedChapter(i, 'start_page', e.target.value)}
                  className="w-16 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-2 py-1.5 text-sm text-[var(--tx1)]" />
                <span className="text-[var(--tx7)] text-xs">–</span>
                <input type="number" value={c.end_page} onChange={e => updateDetectedChapter(i, 'end_page', e.target.value)}
                  className="w-16 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-2 py-1.5 text-sm text-[var(--tx1)]" />
                {c.low_confidence && (
                  <span className="text-amber-400 text-xs px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 shrink-0">{t.teacher.checkEndPage}</span>
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={confirmSplit} disabled={splitting}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                         text-white text-sm font-medium rounded-xl transition-all disabled:opacity-40">
              {splitting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
              {tF(t.teacher.createChaptersBtn, { n: detectedChapters.length })}
            </button>
            <button onClick={useAsOneChapter} disabled={splitting}
              className="px-4 py-2 text-[var(--tx6)] hover:text-[var(--tx2)] text-sm transition-colors disabled:opacity-40">
              {t.teacher.justOneChapter}
            </button>
            <button onClick={cancelDetectedSplit} disabled={splitting}
              className="px-4 py-2 text-[var(--tx7)] hover:text-[var(--tx3)] text-sm transition-colors disabled:opacity-40">
              {t.cancel}
            </button>
          </div>
        </div>
      )}

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
              {unit.chapter_ref && (
                <div className="flex items-center gap-1.5 shrink-0">
                  <button onClick={() => openCropModal(unit.id, unit.chapter_ref!)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-[var(--bd)]
                               text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all">
                    <Crop size={12} /> {t.teacher.fromPdf}
                  </button>
                  <button onClick={() => suggestConcepts(unit.chapter_ref!)} disabled={suggestingFor === unit.chapter_ref}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-[var(--bd)]
                               text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all disabled:opacity-50">
                    {suggestingFor === unit.chapter_ref ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                    {t.teacher.suggestConcepts}
                  </button>
                  <button onClick={() => checkCoverage(unit.chapter_ref!)} disabled={coverageBusy === unit.chapter_ref}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-[var(--bd)]
                               text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all disabled:opacity-50">
                    {coverageBusy === unit.chapter_ref ? <Loader2 size={12} className="animate-spin" /> : <ListChecks size={12} />}
                    {t.teacher.checkCoverage}
                  </button>
                  <button onClick={() => router.push(`/teacher/courses/${courseId}/chapters/${unit.chapter_ref}/studio`)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-purple-500/30
                               text-purple-400 hover:bg-purple-500/10 transition-all">
                    <Wand2 size={12} /> Studio
                  </button>
                </div>
              )}
              <button onClick={() => deleteUnit(unit.id)}
                className="text-[var(--tx8)] hover:text-red-400 transition-colors p-1">
                <Trash2 size={14} />
              </button>
            </div>

            {coverageResult && coverageResult.chapterId === unit.chapter_ref && (
              <div className="mx-5 mb-3 px-3 py-2.5 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl flex items-start justify-between gap-3">
                <p className="text-[var(--tx3)] text-xs whitespace-pre-wrap flex-1">{coverageResult.summary}</p>
                <button onClick={() => setCoverageResult(null)} className="text-[var(--tx8)] hover:text-[var(--tx3)] text-xs shrink-0">✕</button>
              </div>
            )}

            {/* Concepts */}
            {expanded.has(unit.id) && (
              <div className="border-t border-[var(--bd)] px-5 py-3 space-y-1.5">
                {unit.concepts.map((c, ci) => (
                  <div key={c.id} className="flex items-center gap-3 group py-1">
                    <span className="text-[var(--tx8)] text-xs w-5 text-right shrink-0">{ci + 1}.</span>
                    <button
                      onClick={() => router.push(`/teacher/courses/${courseId}/concepts/${c.id}`)}
                      className="flex-1 min-w-0 text-left hover:text-purple-400 transition-colors">
                      <p className="text-[var(--tx2)] text-sm truncate group-hover:text-purple-400 transition-colors flex items-center gap-1.5">
                        {c.title}
                        {c.source === 'manual' && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 shrink-0">{t.teacher.manualBadge}</span>
                        )}
                      </p>
                      <span className="text-xs flex items-center gap-1 mt-0.5">
                        {c.pipeline_status === 'summarizing' && <><Loader2 size={9} className="animate-spin text-amber-400" /><span className="text-amber-400">{t.teacher.statusGenerating}</span></>}
                        {c.pipeline_status === 'ready'       && <><Circle size={9} className="fill-blue-400 text-blue-400" /><span className="text-blue-400">{t.teacher.statusReadyReview}</span></>}
                        {c.pipeline_status === 'approved'    && <><CheckCircle size={9} className="text-green-400" /><span className="text-green-400">{t.teacher.statusApproved}</span></>}
                        {c.pipeline_status === 'failed'      && <span className="text-red-400">{t.teacher.statusFailed}</span>}
                        {(!c.pipeline_status || c.pipeline_status === 'draft') && (
                          c.ss_status === 'ready'
                            ? <span className="text-green-400 flex items-center gap-1"><BookOpen size={9} /> {t.teacher.statusStudySet}</span>
                            : <span className="text-[var(--tx8)]">{t.teacher.statusClickEdit}</span>
                        )}
                      </span>
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
                    <input autoFocus placeholder={t.teacher.addConceptPlaceholder} value={conceptTitle}
                      onChange={e => setConceptTitle(e.target.value)}
                      className={`${inputCls} flex-1`} />
                    <button type="submit"
                      className="px-3 py-1.5 bg-purple-600 text-white text-xs rounded-lg">{t.teacher.addBtn}</button>
                    <button type="button" onClick={() => { setAddingConcept(null); setConceptTitle(''); }}
                      className="px-3 py-1.5 text-[var(--tx7)] text-xs rounded-lg">{t.cancel}</button>
                  </form>
                ) : (
                  <button onClick={() => { setAddingConcept(unit.id); setConceptTitle(''); }}
                    className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-purple-400 text-xs
                               transition-colors mt-1 py-1">
                    <Plus size={12} /> {t.teacher.addConceptBtn}
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
              className="px-3 py-2 bg-purple-600 text-white text-sm rounded-xl">{t.teacher.addBtn}</button>
            <button type="button" onClick={() => { setAddingUnit(false); setUnitTitle(''); }}
              className="px-3 py-2 text-[var(--tx7)] text-sm rounded-xl">{t.cancel}</button>
          </form>
        ) : (
          <button onClick={() => setAddingUnit(true)}
            className="w-full flex items-center justify-center gap-2 py-3 border border-dashed
                       border-[var(--bd)] hover:border-purple-500/40 rounded-2xl text-[var(--tx7)]
                       hover:text-purple-400 text-sm transition-all">
            <Plus size={15} /> {t.teacher.addUnitBtn}
          </button>
        )}
      </div>

      {/* Assign to classrooms */}
      {myClassrooms.length > 0 && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Users size={16} className="text-[var(--tx6)]" />
            <p className="text-[var(--tx2)] text-sm font-medium">{t.teacher.assignToClassrooms}</p>
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
                    {assigned ? <><Check size={11} /> {t.teacher.assignedBadge}</> : <><Plus size={11} /> {t.teacher.assignBadge}</>}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {cropTarget && (
        <PDFViewerModal
          file={cropTarget.file}
          onClose={() => setCropTarget(null)}
          onAsk={() => {}}
          unlimitedPages
          actions={[{
            label: 'Create concept from this',
            icon: Sparkles,
            primary: true,
            onClick: (imageDataUrl) => createConceptFromRegion(cropTarget.unitId, cropTarget.chapterRefId, imageDataUrl),
          }]}
        />
      )}
    </div>
  );
}
