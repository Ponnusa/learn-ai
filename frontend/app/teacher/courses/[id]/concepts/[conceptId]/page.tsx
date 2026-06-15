'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, BookOpen, Upload, Trash2, ImageIcon,
  Loader2, Check, ExternalLink, Plus, FileText, Mic2,
  CheckCircle, Circle, AlertCircle,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Tab = 'source' | 'summary' | 'transcript' | 'images' | 'studyset';
type PipelineStatus = 'draft' | 'summarizing' | 'ready' | 'approved' | 'failed';

interface ConceptImage { id: string; url: string; caption: string; }
interface ConceptDetail {
  id: string; title: string; description?: string;
  content_text?: string; study_set_id?: string; course_id: string;
  source_text?: string; ai_summary?: string; ai_transcript?: string;
  pipeline_status: PipelineStatus; approved_at?: string;
  images: ConceptImage[];
}

const STATUS_LABEL: Record<PipelineStatus, string> = {
  draft:       'No pipeline',
  summarizing: 'Generating…',
  ready:       'Ready for review',
  approved:    'Approved',
  failed:      'Generation failed',
};

export default function ConceptEditorPage() {
  const router    = useRouter();
  const params    = useParams();
  const courseId  = params.id        as string;
  const conceptId = params.conceptId as string;
  const { user, token } = useSessionStore();

  const [concept,      setConcept]      = useState<ConceptDetail | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [activeTab,    setActiveTab]    = useState<Tab>('summary');
  const [leftPanel,    setLeftPanel]    = useState<'source' | 'pdf'>('source');
  const [showLeft,     setShowLeft]     = useState(true);

  // Summary / transcript editing
  const [summary,      setSummary]      = useState('');
  const [transcript,   setTranscript]   = useState('');
  const [savingSum,    setSavingSum]    = useState(false);
  const [savedSum,     setSavedSum]     = useState(false);
  const [savingTr,     setSavingTr]     = useState(false);
  const [savedTr,      setSavedTr]      = useState(false);
  const [approving,    setApproving]    = useState(false);

  // PDF
  const [pdfUrl,       setPdfUrl]       = useState<string | null>(null);
  const [pdfReady,     setPdfReady]     = useState(false);
  const pdfObjectRef = useRef<string | null>(null);

  // Images
  const [uploading,    setUploading]    = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Study set
  const [creatingStudySet, setCreatingStudySet] = useState(false);

  // Polling when summarizing
  const [polling, setPolling] = useState(false);

  const authH = { Authorization: `Bearer ${token}` };
  const jsonH = { ...authH, 'Content-Type': 'application/json' };

  const loadConcept = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authH });
    if (res.ok) {
      const d: ConceptDetail = await res.json();
      setConcept(d);
      setSummary(d.ai_summary || d.content_text || '');
      setTranscript(d.ai_transcript || '');
      if (d.source_text) setLeftPanel('source');
      if (d.pipeline_status === 'summarizing') setPolling(true);
    }
    setLoading(false);
  }, [conceptId, token]);

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    loadConcept();
    loadPdf();
    return () => { if (pdfObjectRef.current) URL.revokeObjectURL(pdfObjectRef.current); };
  }, [user]);

  // Poll while AI is generating
  useEffect(() => {
    if (!polling) return;
    const iv = setInterval(async () => {
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authH });
      if (!res.ok) return;
      const d: ConceptDetail = await res.json();
      if (d.pipeline_status !== 'summarizing') {
        setConcept(d);
        setSummary(d.ai_summary || '');
        setTranscript(d.ai_transcript || '');
        setPolling(false);
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [polling, conceptId, token]);

  async function loadPdf() {
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/syllabus`, { headers: authH });
      if (res.ok) {
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        pdfObjectRef.current = url;
        setPdfUrl(url);
      }
    } finally { setPdfReady(true); }
  }

  async function saveSummary() {
    setSavingSum(true); setSavedSum(false);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
      method: 'PATCH', headers: jsonH,
      body: JSON.stringify({ ai_summary: summary }),
    });
    setSavedSum(true); setSavingSum(false);
    setTimeout(() => setSavedSum(false), 2000);
  }

  async function saveTranscript() {
    setSavingTr(true); setSavedTr(false);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
      method: 'PATCH', headers: jsonH,
      body: JSON.stringify({ ai_transcript: transcript }),
    });
    setSavedTr(true); setSavingTr(false);
    setTimeout(() => setSavedTr(false), 2000);
  }

  async function approveConcept() {
    setApproving(true);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
      method: 'PATCH', headers: jsonH,
      body: JSON.stringify({ ai_summary: summary, ai_transcript: transcript, approve: true }),
    });
    setConcept(prev => prev ? { ...prev, pipeline_status: 'approved' } : prev);
    setApproving(false);
  }

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files?.length) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      const fd = new FormData(); fd.append('file', file);
      const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images`, {
        method: 'POST', headers: authH, body: fd,
      });
      if (res.ok) {
        const img: ConceptImage = await res.json();
        setConcept(prev => prev ? { ...prev, images: [...prev.images, img] } : prev);
      }
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function updateCaption(imgId: string, caption: string) {
    setConcept(prev => prev ? { ...prev, images: prev.images.map(i => i.id === imgId ? { ...i, caption } : i) } : prev);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images/${imgId}`, {
      method: 'PATCH', headers: jsonH, body: JSON.stringify({ caption }),
    });
  }

  async function deleteImage(imgId: string) {
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images/${imgId}`, {
      method: 'DELETE', headers: authH,
    });
    setConcept(prev => prev ? { ...prev, images: prev.images.filter(i => i.id !== imgId) } : prev);
  }

  async function createStudySet() {
    if (!concept || !user) return;
    setCreatingStudySet(true);
    try {
      const ssRes = await fetch(`${API_BASE}/api/studysets`, {
        method: 'POST', headers: jsonH,
        body: JSON.stringify({ title: concept.title, user_id: user.id }),
      });
      const ss = await ssRes.json();
      await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
        method: 'PATCH', headers: jsonH,
        body: JSON.stringify({ study_set_id: ss.id }),
      });
      setConcept(prev => prev ? { ...prev, study_set_id: ss.id } : prev);
      router.push(`/study/${ss.id}`);
    } catch { setCreatingStudySet(false); }
  }

  if (loading) return (
    <div className="h-full flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!concept) return null;

  const status = concept.pipeline_status;
  const isGenerating = status === 'summarizing';
  const isApproved   = status === 'approved';
  const hasPipeline  = status !== 'draft';
  const wordCount    = transcript.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="h-full flex overflow-hidden">

      {/* ── Left panel ───────────────────────────────────────── */}
      <div className={`border-r border-[var(--bd)] flex flex-col overflow-hidden transition-all duration-200 ${showLeft ? 'w-2/5' : 'w-0'}`}>
        {showLeft && (
          <>
            {/* Toggle */}
            <div className="flex border-b border-[var(--bd)] shrink-0">
              {(['source', 'pdf'] as const).map(p => (
                <button key={p} onClick={() => setLeftPanel(p)}
                  className={`flex-1 py-2 text-xs font-medium transition-colors ${leftPanel === p
                    ? 'text-purple-400 border-b-2 border-purple-400'
                    : 'text-[var(--tx7)] hover:text-[var(--tx3)]'}`}>
                  {p === 'source' ? '📄 Source text' : '📑 Full PDF'}
                </button>
              ))}
            </div>

            {leftPanel === 'source' ? (
              concept.source_text ? (
                <div className="flex-1 overflow-y-auto p-4">
                  <p className="text-[var(--tx8)] text-xs mb-3 uppercase tracking-wider font-medium">
                    What AI read for this concept
                  </p>
                  <p className="text-[var(--tx3)] text-sm leading-relaxed whitespace-pre-wrap">
                    {concept.source_text}
                  </p>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center gap-2 text-[var(--tx7)] p-6 text-center">
                  <FileText size={28} />
                  <p className="text-sm">No source text</p>
                  <p className="text-xs text-[var(--tx8)]">Upload a chapter PDF to let AI extract and map source content per concept</p>
                </div>
              )
            ) : (
              pdfUrl
                ? <iframe src={pdfUrl} className="flex-1 w-full" title="Course PDF" />
                : (
                  <div className="flex-1 flex flex-col items-center justify-center gap-2 text-[var(--tx7)] p-6 text-center">
                    {!pdfReady
                      ? <Loader2 size={20} className="animate-spin text-purple-400" />
                      : <><FileText size={28} /><p className="text-sm">No PDF on file</p></>}
                  </div>
                )
            )}
          </>
        )}
      </div>

      {/* ── Right panel ──────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-2xl mx-auto">

          {/* Nav */}
          <div className="flex items-center justify-between mb-5">
            <button onClick={() => router.push(`/teacher/courses/${courseId}`)}
              className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm transition-colors">
              <ArrowLeft size={15} /> Back to course
            </button>
            <button onClick={() => setShowLeft(p => !p)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                         bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] transition-colors">
              <BookOpen size={13} />{showLeft ? 'Hide' : 'Show'} panel
            </button>
          </div>

          {/* Title + status */}
          <div className="mb-5">
            <h1 className="text-[var(--tx1)] text-xl font-bold">{concept.title}</h1>
            {concept.description && <p className="text-[var(--tx6)] text-sm mt-0.5">{concept.description}</p>}
            {hasPipeline && (
              <span className={`inline-flex items-center gap-1.5 mt-2 text-xs px-2.5 py-1 rounded-full font-medium ${
                isApproved   ? 'bg-green-500/15 text-green-400' :
                isGenerating ? 'bg-amber-500/15 text-amber-400' :
                status === 'failed' ? 'bg-red-500/15 text-red-400' :
                'bg-blue-500/15 text-blue-400'
              }`}>
                {isGenerating && <Loader2 size={10} className="animate-spin" />}
                {isApproved   && <CheckCircle size={10} />}
                {status === 'ready' && <Circle size={10} className="fill-blue-400" />}
                {STATUS_LABEL[status]}
              </span>
            )}
          </div>

          {/* Tab bar */}
          <div className="flex gap-1 border-b border-[var(--bd)] mb-6">
            {([
              ['summary',    'Summary',    BookOpen],
              ['transcript', 'Transcript', Mic2],
              ['images',     'Images',     ImageIcon],
              ['studyset',   'Study Set',  ExternalLink],
            ] as const).map(([t, label, Icon]) => (
              <button key={t} onClick={() => setActiveTab(t)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors ${
                  activeTab === t
                    ? 'text-purple-400 border-purple-400'
                    : 'text-[var(--tx7)] border-transparent hover:text-[var(--tx3)]'
                }`}>
                <Icon size={12} />{label}
              </button>
            ))}
          </div>

          {/* ── Summary tab ── */}
          {activeTab === 'summary' && (
            <div>
              {isGenerating ? (
                <div className="flex flex-col items-center gap-3 py-16 text-[var(--tx7)]">
                  <Loader2 size={28} className="text-purple-400 animate-spin" />
                  <p className="text-sm">AI is writing the summary…</p>
                  <p className="text-xs text-[var(--tx8)]">This usually takes 20–40 seconds per concept</p>
                </div>
              ) : status === 'failed' ? (
                <div className="flex flex-col items-center gap-2 py-12 text-red-400">
                  <AlertCircle size={28} />
                  <p className="text-sm">Generation failed. You can write the summary manually below.</p>
                </div>
              ) : null}

              {!isGenerating && (
                <>
                  <label className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider block mb-2">
                    {hasPipeline ? 'AI-generated summary — edit freely' : 'Summary for students'}
                  </label>
                  <textarea
                    value={summary}
                    onChange={e => setSummary(e.target.value)}
                    placeholder="Write a student-friendly explanation of this concept…"
                    rows={12}
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-3
                               text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60
                               resize-y transition-colors leading-relaxed"
                  />
                  <div className="flex items-center gap-3 mt-3">
                    <button onClick={saveSummary} disabled={savingSum}
                      className="flex items-center gap-2 px-4 py-2 bg-[var(--ov2)] hover:bg-[var(--ov3)]
                                 text-[var(--tx2)] text-sm rounded-xl transition-all disabled:opacity-40">
                      {savingSum ? <Loader2 size={13} className="animate-spin" /> : savedSum ? <Check size={13} className="text-green-400" /> : null}
                      {savingSum ? 'Saving…' : savedSum ? 'Saved!' : 'Save'}
                    </button>

                    {(status === 'ready' || status === 'failed' || status === 'draft') && (
                      <button onClick={approveConcept} disabled={approving}
                        className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500
                                   text-white text-sm font-medium rounded-xl transition-all disabled:opacity-40">
                        {approving ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                        {approving ? 'Approving…' : 'Approve concept'}
                      </button>
                    )}

                    {isApproved && (
                      <span className="flex items-center gap-1.5 text-green-400 text-sm">
                        <CheckCircle size={14} /> Approved
                      </span>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── Transcript tab ── */}
          {activeTab === 'transcript' && (
            <div>
              {isGenerating ? (
                <div className="flex flex-col items-center gap-3 py-16 text-[var(--tx7)]">
                  <Loader2 size={28} className="text-purple-400 animate-spin" />
                  <p className="text-sm">AI is writing the transcript…</p>
                </div>
              ) : (
                <>
                  <label className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider block mb-2">
                    Video narration script
                  </label>
                  <textarea
                    value={transcript}
                    onChange={e => setTranscript(e.target.value)}
                    placeholder="Write a spoken-word script for a 2-minute video…"
                    rows={14}
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-3
                               text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60
                               resize-y transition-colors leading-relaxed font-mono"
                  />
                  <div className="flex items-center justify-between mt-2">
                    <p className="text-[var(--tx8)] text-xs">{wordCount} words · ~{Math.round(wordCount / 130)} min read aloud</p>
                    <button onClick={saveTranscript} disabled={savingTr}
                      className="flex items-center gap-2 px-4 py-2 bg-[var(--ov2)] hover:bg-[var(--ov3)]
                                 text-[var(--tx2)] text-sm rounded-xl transition-all disabled:opacity-40">
                      {savingTr ? <Loader2 size={13} className="animate-spin" /> : savedTr ? <Check size={13} className="text-green-400" /> : null}
                      {savingTr ? 'Saving…' : savedTr ? 'Saved!' : 'Save'}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── Images tab ── */}
          {activeTab === 'images' && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider">Images</label>
                <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                             bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] transition-colors disabled:opacity-40">
                  {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />} Upload
                </button>
                <input ref={fileInputRef} type="file" accept="image/*" multiple className="hidden" onChange={handleImageUpload} />
              </div>
              {concept.images.length === 0 ? (
                <div className="border border-dashed border-[var(--bd)] rounded-xl p-10 text-center">
                  <ImageIcon size={24} className="text-[var(--tx8)] mx-auto mb-2" />
                  <p className="text-[var(--tx7)] text-sm">No images yet</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {concept.images.map(img => (
                    <div key={img.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                      <div className="relative aspect-video bg-[var(--ov2)]">
                        <img src={`${API_BASE}${img.url}`} alt={img.caption} className="w-full h-full object-contain" />
                        <button onClick={() => deleteImage(img.id)}
                          className="absolute top-2 right-2 p-1 bg-red-500/80 hover:bg-red-500 text-white rounded-lg transition-colors">
                          <Trash2 size={11} />
                        </button>
                      </div>
                      <div className="px-3 py-2 border-t border-[var(--bd)]">
                        <input placeholder="Caption" value={img.caption}
                          onChange={e => updateCaption(img.id, e.target.value)}
                          className="w-full bg-transparent text-xs text-[var(--tx3)] outline-none placeholder:text-[var(--tx8)]" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Study set tab ── */}
          {activeTab === 'studyset' && (
            <div>
              <label className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider block mb-3">Study materials</label>
              {concept.study_set_id ? (
                <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl p-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[var(--tx1)] text-sm font-medium">Study set linked</p>
                    <p className="text-[var(--tx7)] text-xs mt-0.5">Students get videos, PDFs and flashcards from this set</p>
                  </div>
                  <button onClick={() => router.push(`/study/${concept.study_set_id}`)}
                    className="flex items-center gap-1.5 text-sm text-purple-400 hover:text-purple-300 whitespace-nowrap transition-colors">
                    Open <ExternalLink size={13} />
                  </button>
                </div>
              ) : (
                <div className="bg-[var(--surface)] border border-dashed border-[var(--bd)] rounded-xl p-6 text-center">
                  <p className="text-[var(--tx3)] text-sm mb-1">No study materials yet</p>
                  <p className="text-[var(--tx7)] text-xs mb-4">Create a study set to add videos, PDFs and flashcards</p>
                  <button onClick={createStudySet} disabled={creatingStudySet}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                               text-white text-sm font-medium rounded-xl transition-all disabled:opacity-40">
                    {creatingStudySet ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                    Create study materials
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
