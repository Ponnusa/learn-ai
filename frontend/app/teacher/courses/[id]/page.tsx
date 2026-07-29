'use client';
import { useEffect, useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Plus, Trash2, ChevronDown, ChevronRight,
  Upload, Loader2, Check, BookOpen, Users,
  CheckCircle, Globe, Zap, Circle, Crop, Sparkles, Wand2, GripVertical, HelpCircle,
} from 'lucide-react';
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { SortableContext, useSortable, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useSessionStore } from '@/store/sessionStore';
import { PDFViewerModal } from '@/components/chat/PDFViewerModal';
import { CourseDetailTour } from '@/components/onboarding/CourseDetailTour';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type PipelineStatus = 'draft' | 'summarizing' | 'ready' | 'approved' | 'failed';
interface Concept {
  id: string; title: string; description?: string; study_set_id?: string; ss_status?: string;
  pipeline_status?: PipelineStatus; position: number; source?: 'ai' | 'manual';
  chat_msg_count?: number; last_activity_at?: string | null; textbook_block_count?: number;
  quiz_status?: string | null; flashcard_status?: string | null;
  audio_status?: string | null; video_status?: string | null;
}
interface Unit    { id: string; title: string; description?: string; position: number; chapter_ref?: string | null; concepts: Concept[]; }
interface Classroom { id: string; name: string; }
interface Course  {
  id: string; name: string; description?: string;
  subject?: string; grade?: string; status: string;
  units: Unit[]; classrooms: Classroom[];
}

function relTime(iso: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1)    return 'just now';
  if (mins < 60)   return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)    return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30)   return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function assetBadge(status: string | null | undefined, label: string) {
  if (!status || status === 'none') return null;
  const cls =
    status === 'approved'   ? 'text-green-400' :
    status === 'ready'      ? 'text-blue-400'  :
    status === 'failed'     ? 'text-red-400'   : 'text-amber-400';
  const sym =
    status === 'approved'   ? '✓' :
    status === 'ready'      ? '●' :
    status === 'failed'     ? '✗' : '…';
  return <span className={`text-[10px] ${cls}`}>{label} {sym}</span>;
}

type DetectedChapter = { id: string; title: string; start_page: number; end_page: number; low_confidence?: boolean };

function SortableChapterRow({ c, i, onUpdate, onRemove, lowConfidenceLabel, outOfRange }: {
  c: DetectedChapter;
  i: number;
  onUpdate: (i: number, field: 'start_page' | 'end_page' | 'title', value: string) => void;
  onRemove: (i: number) => void;
  lowConfidenceLabel: string;
  outOfRange?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: c.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };
  return (
    <div ref={setNodeRef} style={style} className={`flex items-center gap-2 ${outOfRange ? 'opacity-60' : ''}`}>
      <div {...attributes} {...listeners}
        className="cursor-grab active:cursor-grabbing text-[var(--tx7)] hover:text-[var(--tx3)] p-1 touch-none shrink-0">
        <GripVertical size={14} />
      </div>
      <input value={c.title} onChange={e => onUpdate(i, 'title', e.target.value)}
        className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-2.5 py-1.5 text-sm text-[var(--tx1)]" />
      <span className="text-[var(--tx7)] text-xs">p.</span>
      <input type="number" value={c.start_page} onChange={e => onUpdate(i, 'start_page', e.target.value)}
        className="w-16 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-2 py-1.5 text-sm text-[var(--tx1)]" />
      <span className="text-[var(--tx7)] text-xs">–</span>
      <input type="number" value={c.end_page} onChange={e => onUpdate(i, 'end_page', e.target.value)}
        className="w-16 bg-[var(--ov1)] border border-[var(--bd)] rounded-lg px-2 py-1.5 text-sm text-[var(--tx1)]" />
      {c.low_confidence && (
        <span className="text-amber-400 text-xs px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 shrink-0">
          {lowConfidenceLabel}
        </span>
      )}
      <button onClick={() => onRemove(i)}
        className="p-1.5 text-[var(--tx7)] hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors shrink-0"
        title="Remove">
        <Trash2 size={14} />
      </button>
    </div>
  );
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
    { id: string; title: string; start_page: number; end_page: number; low_confidence?: boolean }[] | null
  >(null);
  const [detectedPageCount, setDetectedPageCount] = useState<number>(0);
  const [pendingNoTocFile, setPendingNoTocFile] = useState<File | null>(null);
  const chapterDndSensors = useSensors(useSensor(PointerSensor));
  const [splitting, setSplitting] = useState(false);

  // Assign to classroom
  const [myClassrooms, setMyClassrooms] = useState<Classroom[]>([]);
  const [assigning,    setAssigning]    = useState(false);

  // Delete confirmation
  const [deleteConfirm, setDeleteConfirm] = useState<{ unitId: string; conceptId: string; title: string } | null>(null);

  // Manual concept creation — crop a region of the chapter PDF as an image
  const [cropTarget, setCropTarget] = useState<{ unitId: string; chapterRefId: string; file: File } | null>(null);
  // Magic-wand bulk generation
  const [wandOpen,  setWandOpen]  = useState<string | null>(null); // chapter_ref_id of open popover
  const [wandTypes, setWandTypes] = useState<Set<string>>(new Set(['summary', 'quiz', 'flashcard', 'audio']));
  const [wandSkip,  setWandSkip]  = useState(true);
  const [wandBusy,  setWandBusy]  = useState<string | null>(null);

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

      // Auto-resume polling if background processing is still running
      // (handles page refresh mid-upload without losing progress).
      const pRes = await fetch(`${API_BASE}/api/courses/${courseId}/pipeline`, { headers });
      if (pRes.ok) {
        const pData = await pRes.json();
        if (pData.is_processing) {
          const c = (pData.counts ?? {}) as Record<string, number>;
          const total = Object.values(c).reduce((a: number, b: number) => a + b, 0);
          const done  = (c.approved ?? 0) + (c.ready ?? 0) + (c.failed ?? 0);
          setTotalCount(total);
          setProcessedCount(done);
          if (!isProcessing) {
            setIsProcessing(true);
            setPipelineMsg('Extracting concepts in the background…');
          }
        }
      }
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
      load();
      if (!data.is_processing) {
        setIsProcessing(false);
        setPipelineMsg('');
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

  async function uploadAndSuggestConcepts(file: File) {
    setPendingNoTocFile(null);
    setUploading(true);
    setPipelineMsg('No chapters found — uploading and scanning content for concepts…');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/chapters`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      setUploading(false);
      await load();

      const chapterId = data.chapter_id;
      setPipelineMsg('Reading content page by page to find concepts…');
      const sRes = await fetch(`${API_BASE}/api/courses/chapters/${chapterId}/suggest-concepts`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      const sData = await sRes.json();
      if (sRes.ok && sData.concept_count > 0) {
        setTotalCount(sData.concept_count);
        setProcessedCount(0);
        setIsProcessing(true);
        setPipelineMsg(`Found ${sData.concept_count} concept${sData.concept_count !== 1 ? 's' : ''} — generating content…`);
        await load();
      } else {
        setPipelineMsg('');
        await load();
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(false);
      if (chapterRef.current) chapterRef.current.value = '';
    }
  }

  function toggleWandType(type: string) {
    setWandTypes(prev => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  }

  async function generateWand(chapterRefId: string) {
    if (wandTypes.size === 0) return;
    setWandBusy(chapterRefId);
    setWandOpen(null);
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/chapters/${chapterRefId}/bulk-generate`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ types: [...wandTypes], skip_existing: wandSkip }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Generation failed');
      setIsProcessing(true);
      setPipelineMsg(`Generating content for ${data.concept_count} concepts in background…`);
      load();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setWandBusy(null);
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
        setDetectedPageCount(data.page_count ?? 0);
        setDetectedChapters(data.chapters.map((c: Omit<typeof data.chapters[0], 'id'>) => ({ ...c, id: crypto.randomUUID() })));
      } else {
        setPendingNoTocFile(file);
      }
    } catch {
      // Detection failing shouldn't block the upload — fall back to today's flow.
      setPendingNoTocFile(file);
    } finally {
      setDetecting(false);
    }
  }

  function updateDetectedChapter(i: number, field: 'start_page' | 'end_page' | 'title', value: string) {
    setDetectedChapters(prev => prev?.map((c, idx) => idx === i
      ? { ...c, [field]: field === 'title' ? value : Number(value) }
      : c) ?? null);
  }

  function removeDetectedChapter(i: number) {
    setDetectedChapters(prev => prev?.filter((_, idx) => idx !== i) ?? null);
  }

  function handleChapterDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setDetectedChapters(prev => {
      if (!prev) return prev;
      const oldIdx = prev.findIndex(c => c.id === active.id);
      const newIdx = prev.findIndex(c => c.id === over.id);
      return arrayMove(prev, oldIdx, newIdx);
    });
  }

  function addDetectedChapter() {
    setDetectedChapters(prev => {
      const list = prev ?? [];
      const lastEnd = list.length > 0 ? list[list.length - 1].end_page : 0;
      return [...list, { id: crypto.randomUUID(), title: '', start_page: lastEnd + 1, end_page: lastEnd + 1 }];
    });
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
      setTotalCount(0);
      setProcessedCount(0);
      setIsProcessing(true);
      setPipelineMsg(`Created ${data.chapter_count ?? data.chapters?.length ?? 0} chapters — extracting concepts in background…`);
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
    setDeleteConfirm(null);
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

      <CourseDetailTour />

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
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('start-course-detail-tour'))}
            className="text-[var(--tx7)] hover:text-purple-400 transition-colors p-1"
            title="Take a tour"
          ><HelpCircle size={14} /></button>
          <button onClick={() => router.push(`/teacher/courses/${courseId}/progress`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all">
            <Users size={14} /> {t.teacher.progressBtn}
          </button>
          <button data-tour="publish-btn" onClick={publish}
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
          <button data-tour="upload-chapter" onClick={() => chapterRef.current?.click()} disabled={uploading || detecting || isProcessing}
            className="shrink-0 flex items-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-500
                       text-white text-sm rounded-xl transition-all disabled:opacity-40">
            {uploading || detecting ? <Loader2 size={14} className="animate-spin" /> : <><Upload size={14} /> {t.teacher.uploadChapterBtn}</>}
          </button>
          <input ref={chapterRef} type="file" accept=".pdf" className="hidden"
            onChange={e => e.target.files?.[0] && handleFileSelected(e.target.files[0])} />
        </div>
      </div>

      {/* No TOC found — offer to scan content for concepts */}
      {pendingNoTocFile && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
          <div className="flex items-start gap-3 mb-4">
            <span className="text-2xl shrink-0">📄</span>
            <div>
              <p className="text-[var(--tx1)] text-sm font-semibold mb-1">No chapter structure detected</p>
              <p className="text-[var(--tx6)] text-xs leading-relaxed">
                This PDF doesn&apos;t have a table of contents or numbered chapters. The AI can still read through the content
                page by page and find key concepts automatically — this may take a minute.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => uploadAndSuggestConcepts(pendingNoTocFile)}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                         text-white text-sm font-medium rounded-xl transition-all">
              <Sparkles size={14} /> Upload &amp; find concepts
            </button>
            <button onClick={() => { setPendingNoTocFile(null); handleChapterUpload(pendingNoTocFile); }}
              className="px-4 py-2 text-[var(--tx6)] hover:text-[var(--tx2)] text-sm transition-colors">
              Upload without concepts
            </button>
            <button onClick={() => { setPendingNoTocFile(null); if (chapterRef.current) chapterRef.current.value = ''; }}
              className="px-4 py-2 text-[var(--tx7)] hover:text-[var(--tx3)] text-sm transition-colors">
              {t.cancel}
            </button>
          </div>
        </div>
      )}

      {/* Detected multi-chapter textbook — review/edit before splitting */}
      {detectedChapters && (
        <div className="bg-[var(--surface)] border border-purple-500/30 rounded-2xl p-5 mb-6">
          <p className="text-[var(--tx1)] text-sm font-semibold mb-1">
            {tF(t.teacher.detectedChapters, { n: detectedChapters.length })}
          </p>
          <p className="text-[var(--tx7)] text-xs mb-4">
            {t.teacher.reviewRanges}
          </p>
          {detectedPageCount > 0 && detectedChapters.some(c => c.start_page > detectedPageCount) && (
            <div className="mb-4 flex gap-2 items-start bg-amber-500/10 border border-amber-500/30 rounded-xl px-3 py-2.5 text-amber-400 text-xs">
              <span className="shrink-0 mt-0.5">⚠️</span>
              <span>
                This PDF only has <strong>{detectedPageCount} pages</strong>, but some chapters reference pages beyond that.
                You may have uploaded only part of the textbook — chapters with a start page above {detectedPageCount} will produce empty results.
                Upload the full textbook PDF to get all chapters.
              </span>
            </div>
          )}
          <DndContext sensors={chapterDndSensors} collisionDetection={closestCenter} onDragEnd={handleChapterDragEnd}>
            <SortableContext items={detectedChapters.map(c => c.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2 mb-4">
                {detectedChapters.map((c, i) => (
                  <SortableChapterRow key={c.id} c={c} i={i}
                    onUpdate={updateDetectedChapter}
                    onRemove={removeDetectedChapter}
                    lowConfidenceLabel={t.teacher.checkEndPage}
                    outOfRange={detectedPageCount > 0 && c.start_page > detectedPageCount} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
          <button onClick={addDetectedChapter} disabled={splitting}
            className="flex items-center gap-1.5 text-[var(--tx6)] hover:text-[var(--tx2)] text-xs mb-4 transition-colors disabled:opacity-40">
            <Plus size={13} />
            Add chapter manually
          </button>
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
                  {/* Magic-wand button */}
                  <div className="relative">
                    {unit.concepts.length === 0 && (
                      <span className="absolute -top-1.5 -left-1.5 w-3 h-3 rounded-full bg-amber-400 ring-2 ring-[var(--bg)] z-10" title="No concepts extracted yet" />
                    )}
                    <button
                      onClick={() => {
                        if (unit.concepts.length === 0) {
                          setWandTypes(new Set(['suggest', 'summary', 'quiz', 'flashcard', 'audio']));
                        }
                        setWandOpen(unit.chapter_ref!);
                      }}
                      disabled={wandBusy === unit.chapter_ref}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-[var(--bd)]
                                 text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all disabled:opacity-50">
                      {wandBusy === unit.chapter_ref
                        ? <Loader2 size={12} className="animate-spin" />
                        : <Wand2 size={12} />}
                      {t.teacher.wandGenerate}
                    </button>
                  </div>
                </div>
              )}
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
                      {/* Activity strip */}
                      {c.chat_msg_count !== undefined && (
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          <span className={`flex items-center gap-0.5 text-[10px] ${
                            (c.chat_msg_count ?? 0) > 0 ? 'text-violet-400' : 'text-[var(--tx8)]'
                          }`}>
                            <Wand2 size={8} />
                            {(c.chat_msg_count ?? 0) > 0
                              ? `${c.chat_msg_count} msg${c.chat_msg_count !== 1 ? 's' : ''}`
                              : '—'}
                          </span>
                          {assetBadge(c.video_status, 'Video')}
                          {assetBadge(c.audio_status, 'Audio')}
                          {assetBadge(c.quiz_status,  'Quiz')}
                          {(c.textbook_block_count ?? 0) > 0 && (
                            <span className="text-[10px] text-purple-400">
                              {c.textbook_block_count} block{c.textbook_block_count !== 1 ? 's' : ''}
                            </span>
                          )}
                          {c.last_activity_at && (
                            <span className="text-[10px] text-[var(--tx8)]">{relTime(c.last_activity_at)}</span>
                          )}
                        </div>
                      )}
                    </button>
                    <button onClick={() => setDeleteConfirm({ unitId: unit.id, conceptId: c.id, title: c.title })}
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
          <button data-tour="add-unit" onClick={() => setAddingUnit(true)}
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

      {deleteConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => setDeleteConfirm(null)}>
          <div className="bg-[var(--bg2)] border border-[var(--bd)] rounded-2xl p-6 w-80 shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <p className="text-[var(--tx1)] font-semibold mb-1">Delete concept?</p>
            <p className="text-[var(--tx6)] text-sm mb-5 break-words">
              &ldquo;{deleteConfirm.title}&rdquo; and all its content will be permanently removed.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 text-sm text-[var(--tx6)] hover:text-[var(--tx2)] transition-colors">
                Cancel
              </button>
              <button onClick={() => deleteConcept(deleteConfirm.unitId, deleteConfirm.conceptId)}
                className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-500 text-white rounded-xl transition-colors">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Magic-wand modal */}
      {wandOpen && (() => {
        const wandUnit = course?.units.find((u: Unit) => u.chapter_ref === wandOpen);
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setWandOpen(null)}>
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
            <div
              className="relative w-full max-w-sm rounded-2xl border border-[var(--bd)] bg-[var(--surface)] shadow-2xl p-5"
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs text-[var(--tx6)] mb-0.5">{wandUnit?.title}</p>
                  <h3 className="text-sm font-semibold text-[var(--tx1)] flex items-center gap-1.5">
                    <Wand2 size={14} className="text-purple-400" /> {t.teacher.wandGenerate}
                  </h3>
                </div>
                <button onClick={() => setWandOpen(null)} className="text-[var(--tx6)] hover:text-[var(--tx1)] transition-colors text-lg leading-none">✕</button>
              </div>

              {/* Asset type checkboxes */}
              <div className="space-y-3">
                {([
                  ['summary',   t.teacher.wandSummary,   null],
                  ['quiz',      t.teacher.wandQuiz,       null],
                  ['flashcard', t.teacher.wandFlashcard,  null],
                  ['audio',     t.teacher.wandAudio,      null],
                  ['video',     t.teacher.wandVideo,      t.teacher.wandVideoWarn],
                  ['suggest',   t.teacher.wandSuggest,    null],
                ] as [string, string, string | null][]).map(([type, label, warn]) => (
                  <label key={type} className="flex items-center gap-3 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={wandTypes.has(type)}
                      onChange={() => toggleWandType(type)}
                      className="accent-purple-500 w-4 h-4 shrink-0"
                    />
                    <span className="text-sm text-[var(--tx3)] group-hover:text-[var(--tx1)] transition-colors flex items-center gap-2">
                      {label}
                      {warn && <span className="text-xs text-amber-400/80">{warn}</span>}
                    </span>
                  </label>
                ))}
              </div>

              {/* Skip existing toggle */}
              <div className="border-t border-[var(--bd)] mt-4 pt-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={wandSkip}
                    onChange={e => setWandSkip(e.target.checked)}
                    className="accent-purple-500 w-4 h-4 shrink-0"
                  />
                  <span className="text-sm text-[var(--tx6)]">{t.teacher.wandSkipExisting}</span>
                </label>
              </div>

              {/* Generate button */}
              <button
                onClick={() => generateWand(wandOpen)}
                disabled={wandTypes.size === 0}
                className="mt-4 w-full py-2 text-sm rounded-xl bg-purple-600 hover:bg-purple-500
                           text-white font-medium transition-colors disabled:opacity-40 flex items-center justify-center gap-2">
                <Sparkles size={13} /> {t.teacher.wandGenerateBtn}
              </button>
            </div>
          </div>
        );
      })()}

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
