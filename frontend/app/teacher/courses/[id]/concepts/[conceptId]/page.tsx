'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, BookOpen, Upload, Trash2, ImageIcon,
  Loader2, Check, ExternalLink, Plus, FileText,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ConceptImage { id: string; url: string; caption: string; }
interface ConceptDetail {
  id: string; title: string; description?: string;
  content_text?: string; study_set_id?: string;
  course_id: string; images: ConceptImage[];
}

export default function ConceptEditorPage() {
  const router     = useRouter();
  const params     = useParams();
  const courseId   = params.id        as string;
  const conceptId  = params.conceptId as string;
  const { user, token } = useSessionStore();

  const [concept,   setConcept]   = useState<ConceptDetail | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [text,      setText]      = useState('');
  const [saving,    setSaving]    = useState(false);
  const [saved,     setSaved]     = useState(false);
  const [pdfUrl,    setPdfUrl]    = useState<string | null>(null);
  const [pdfReady,  setPdfReady]  = useState(false);
  const [showPdf,   setShowPdf]   = useState(true);
  const [uploading, setUploading] = useState(false);
  const [creatingStudySet, setCreatingStudySet] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pdfObjectRef = useRef<string | null>(null);

  const authHeaders = { Authorization: `Bearer ${token}` };
  const jsonHeaders = { ...authHeaders, 'Content-Type': 'application/json' };

  const loadConcept = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, { headers: authHeaders });
    if (res.ok) {
      const d: ConceptDetail = await res.json();
      setConcept(d);
      setText(d.content_text || '');
    }
    setLoading(false);
  }, [conceptId, token]);

  const loadPdf = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/syllabus`, { headers: authHeaders });
      if (res.ok) {
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        pdfObjectRef.current = url;
        setPdfUrl(url);
      }
    } finally { setPdfReady(true); }
  }, [courseId, token]);

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    loadConcept();
    loadPdf();
    return () => { if (pdfObjectRef.current) URL.revokeObjectURL(pdfObjectRef.current); };
  }, [user]);

  async function save() {
    if (!concept) return;
    setSaving(true); setSaved(false);
    try {
      await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
        method: 'PATCH', headers: jsonHeaders,
        body: JSON.stringify({ content_text: text }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  }

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const fd = new FormData();
        fd.append('file', file);
        const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images`, {
          method: 'POST', headers: authHeaders, body: fd,
        });
        if (res.ok) {
          const img: ConceptImage = await res.json();
          setConcept(prev => prev ? { ...prev, images: [...prev.images, img] } : prev);
        }
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function updateCaption(imgId: string, caption: string) {
    setConcept(prev => prev ? {
      ...prev, images: prev.images.map(i => i.id === imgId ? { ...i, caption } : i),
    } : prev);
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images/${imgId}`, {
      method: 'PATCH', headers: jsonHeaders, body: JSON.stringify({ caption }),
    });
  }

  async function deleteImage(imgId: string) {
    await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/images/${imgId}`, {
      method: 'DELETE', headers: authHeaders,
    });
    setConcept(prev => prev ? { ...prev, images: prev.images.filter(i => i.id !== imgId) } : prev);
  }

  async function createStudySet() {
    if (!concept || !user) return;
    setCreatingStudySet(true);
    try {
      const ssRes = await fetch(`${API_BASE}/api/studysets`, {
        method: 'POST', headers: jsonHeaders,
        body: JSON.stringify({ title: concept.title, user_id: user.id, description: concept.description || '' }),
      });
      if (!ssRes.ok) throw new Error();
      const ss = await ssRes.json();

      await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/detail`, {
        method: 'PATCH', headers: jsonHeaders,
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

  return (
    <div className="h-full flex overflow-hidden">

      {/* ── Left: syllabus PDF ───────────────────────────────────────── */}
      <div className={`border-r border-[var(--bd)] flex flex-col overflow-hidden transition-all duration-200 ${showPdf ? 'w-2/5' : 'w-0'}`}>
        {showPdf && (
          pdfUrl
            ? <iframe src={pdfUrl} className="flex-1 w-full" title="Syllabus PDF" />
            : (
              <div className="flex-1 flex flex-col items-center justify-center gap-3 text-[var(--tx7)] px-6 text-center">
                {!pdfReady
                  ? <Loader2 size={20} className="animate-spin text-purple-400" />
                  : <>
                      <FileText size={32} />
                      <p className="text-sm">No syllabus PDF for this course</p>
                      <p className="text-xs text-[var(--tx8)]">Import a PDF in the course builder to view it here</p>
                    </>
                }
              </div>
            )
        )}
      </div>

      {/* ── Right: editor ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 max-w-2xl mx-auto">

          {/* Nav */}
          <div className="flex items-center justify-between mb-6">
            <button onClick={() => router.push(`/teacher/courses/${courseId}`)}
              className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm transition-colors">
              <ArrowLeft size={15} /> Back to course
            </button>
            <button onClick={() => setShowPdf(p => !p)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                         bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)] transition-colors">
              <BookOpen size={13} />
              {showPdf ? 'Hide' : 'Show'} syllabus
            </button>
          </div>

          {/* Title */}
          <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{concept.title}</h1>
          {concept.description && (
            <p className="text-[var(--tx6)] text-sm mb-6">{concept.description}</p>
          )}

          {/* Explanation */}
          <section className="mb-8">
            <label className="text-[var(--tx2)] text-sm font-semibold block mb-2">
              Explanation for students
            </label>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Write an explanation — students read this before starting the study materials. Markdown is supported."
              rows={10}
              className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-3
                         text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60
                         resize-y transition-colors leading-relaxed font-mono"
            />
            <button onClick={save} disabled={saving}
              className="mt-2 flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                         text-white text-sm font-medium rounded-xl transition-all disabled:opacity-40">
              {saving   ? <Loader2 size={14} className="animate-spin" />
               : saved  ? <Check   size={14} />
               : null}
              {saving ? 'Saving…' : saved ? 'Saved!' : 'Save explanation'}
            </button>
          </section>

          {/* Images */}
          <section className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <label className="text-[var(--tx2)] text-sm font-semibold">Images</label>
              <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                           bg-[var(--ov1)] hover:bg-[var(--ov2)] text-[var(--tx3)]
                           transition-colors disabled:opacity-40">
                {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
                Upload
              </button>
              <input ref={fileInputRef} type="file" accept="image/*" multiple
                className="hidden" onChange={handleImageUpload} />
            </div>

            {concept.images.length === 0 && !uploading && (
              <div className="border border-dashed border-[var(--bd)] rounded-xl p-8 text-center">
                <ImageIcon size={24} className="text-[var(--tx8)] mx-auto mb-2" />
                <p className="text-[var(--tx7)] text-sm">No images yet</p>
                <p className="text-[var(--tx8)] text-xs mt-0.5">Upload diagrams or illustrations to help students</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              {concept.images.map(img => (
                <div key={img.id}
                  className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl overflow-hidden">
                  <div className="relative aspect-video bg-[var(--ov2)]">
                    <img src={`${API_BASE}${img.url}`} alt={img.caption}
                      className="w-full h-full object-contain" />
                    <button onClick={() => deleteImage(img.id)}
                      className="absolute top-2 right-2 p-1 bg-red-500/80 hover:bg-red-500
                                 text-white rounded-lg transition-colors">
                      <Trash2 size={11} />
                    </button>
                  </div>
                  <div className="px-3 py-2 border-t border-[var(--bd)]">
                    <input
                      placeholder="Caption (optional)"
                      value={img.caption}
                      onChange={e => updateCaption(img.id, e.target.value)}
                      className="w-full bg-transparent text-xs text-[var(--tx3)] outline-none
                                 placeholder:text-[var(--tx8)]"
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Study set */}
          <section className="mb-8">
            <label className="text-[var(--tx2)] text-sm font-semibold block mb-3">Study materials</label>
            {concept.study_set_id ? (
              <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl p-4
                              flex items-center justify-between gap-4">
                <div>
                  <p className="text-[var(--tx1)] text-sm font-medium">Study set linked</p>
                  <p className="text-[var(--tx7)] text-xs mt-0.5">
                    Students access videos and flashcards from this study set
                  </p>
                </div>
                <button onClick={() => router.push(`/study/${concept.study_set_id}`)}
                  className="flex items-center gap-1.5 text-sm text-purple-400 hover:text-purple-300
                             whitespace-nowrap transition-colors">
                  Open <ExternalLink size={13} />
                </button>
              </div>
            ) : (
              <div className="bg-[var(--surface)] border border-dashed border-[var(--bd)]
                              rounded-xl p-5 text-center">
                <p className="text-[var(--tx3)] text-sm mb-1">No study materials yet</p>
                <p className="text-[var(--tx7)] text-xs mb-4">
                  Create a study set to add videos, PDFs and flashcards for students
                </p>
                <button onClick={createStudySet} disabled={creatingStudySet}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500
                             text-white text-sm font-medium rounded-xl transition-all disabled:opacity-40">
                  {creatingStudySet ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  Create study materials
                </button>
              </div>
            )}
          </section>

        </div>
      </div>
    </div>
  );
}
