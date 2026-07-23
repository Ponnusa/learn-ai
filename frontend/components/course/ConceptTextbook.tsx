'use client';
import { useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import {
  Loader2, Video, Volume2, Trash2, Mic2, GripVertical, Save, Check,
  Pencil, X, FileText, ImageIcon, ExternalLink,
} from 'lucide-react';
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext, useSortable, verticalListSortingStrategy, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  ContentBlock, listContentBlocks, deleteContentBlock,
  generateBlockAudio, reorderContentBlocks, updateContentBlock,
} from '@/lib/api';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseVideoEmbed(url: string): { isYoutube: boolean; embedUrl: string } {
  const yt = url.match(
    /(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/,
  );
  if (yt) return { isYoutube: true, embedUrl: `https://www.youtube.com/embed/${yt[1]}` };
  return { isYoutube: false, embedUrl: url };
}

function resourceUrl(bodyOrId: string): string {
  if (!bodyOrId) return '';
  if (bodyOrId.startsWith('http')) return bodyOrId;
  return `${API_BASE}/api/courses/concepts/resources/${bodyOrId}/file`;
}

// ── Block sub-components ──────────────────────────────────────────────────────

function VideoBlock({ block, token }: { block: ContentBlock; token?: string }) {
  const [videoUrl, setVideoUrl] = useState(block.video_url);
  const [status,   setStatus]   = useState(block.video_status);
  const [polling,  setPolling]  = useState(!block.video_url && !!block.video_id);

  useEffect(() => {
    if (!polling || !block.video_id) return;
    let alive = true;
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/videos/${block.video_id}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok || !alive) return;
        const d = await res.json();
        setStatus(d.status);
        if (d.url) { setVideoUrl(d.url); setPolling(false); }
        if (d.status === 'failed') setPolling(false);
      } catch { /* ignore */ }
    }, 5000);
    return () => { alive = false; clearInterval(iv); };
  }, [polling, block.video_id, token]);

  return (
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
        <Video size={14} className="text-purple-400" />
        <span className="text-sm font-medium text-[var(--tx2)]">{block.title || 'Video'}</span>
      </div>
      {videoUrl
        ? <video src={videoUrl} controls className="w-full aspect-video bg-black" preload="metadata" />
        : <div className="flex flex-col items-center justify-center gap-2 py-10 text-[var(--tx7)]">
            {status === 'failed'
              ? <p className="text-sm text-red-400">Video generation failed</p>
              : <><Loader2 size={20} className="animate-spin text-purple-400" />
                  <p className="text-xs">{
                    status === 'transcript_ready' ? 'Writing animation code…' :
                    status === 'queued'           ? 'Rendering video…' :
                    status === 'rendering'        ? 'Rendering video…' : 'Generating video…'
                  }</p></>}
          </div>}
    </div>
  );
}

function AudioBlock({ block }: { block: ContentBlock }) {
  return (
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
        <Volume2 size={14} className="text-blue-400" />
        <span className="text-sm font-medium text-[var(--tx2)]">{block.title || 'Audio'}</span>
      </div>
      <div className="px-4 py-3">
        <audio controls src={block.body || ''} className="w-full" />
      </div>
    </div>
  );
}

function EmbedVideoBlock({ block }: { block: ContentBlock }) {
  const { isYoutube, embedUrl } = parseVideoEmbed(block.body || '');
  return (
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden">
      {block.title && (
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
          <Video size={14} className="text-purple-400" />
          <span className="text-sm font-medium text-[var(--tx2)]">{block.title}</span>
        </div>
      )}
      {isYoutube
        ? <iframe src={embedUrl} className="w-full aspect-video" allowFullScreen
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" />
        : <video src={embedUrl} controls className="w-full aspect-video bg-black" />}
    </div>
  );
}

function EmbedImageBlock({
  block, onLightbox,
}: { block: ContentBlock; onLightbox: (url: string) => void }) {
  const url = resourceUrl(block.body || '');
  return (
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden cursor-zoom-in group"
      onClick={() => onLightbox(url)}>
      {block.title && (
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
          <ImageIcon size={14} className="text-blue-400" />
          <span className="text-sm font-medium text-[var(--tx2)]">{block.title}</span>
        </div>
      )}
      <div className="relative bg-[var(--ov2)] max-h-80 flex items-center justify-center overflow-hidden">
        <img src={url} alt={block.title || 'Image'}
          className="max-w-full max-h-80 object-contain transition-transform group-hover:scale-[1.02]" />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
        <span className="absolute bottom-2 right-2 text-[10px] text-white bg-black/40 px-2 py-0.5 rounded-full
                         opacity-0 group-hover:opacity-100 transition-opacity">
          Click to enlarge
        </span>
      </div>
    </div>
  );
}

function EmbedPdfBlock({
  block, onOpen,
}: { block: ContentBlock; onOpen: (url: string, title: string) => void }) {
  const url = resourceUrl(block.body || '');
  const title = block.title || 'PDF Document';
  return (
    <div className="rounded-xl border border-[var(--bd)] bg-[var(--ov1)] overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3.5">
        <FileText size={22} className="text-red-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[var(--tx2)]">{title}</p>
          <p className="text-xs text-[var(--tx7)]">PDF — click to open</p>
        </div>
        <button onClick={() => onOpen(url, title)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                     bg-[var(--surface)] border border-[var(--bd)] text-[var(--tx3)]
                     hover:border-purple-500/40 hover:text-purple-400 transition-colors">
          <ExternalLink size={11} /> Open PDF
        </button>
      </div>
    </div>
  );
}

interface TextBlockProps {
  block: ContentBlock; conceptId: string; token?: string; editable?: boolean;
}
function TextBlock({ block, conceptId, token, editable }: TextBlockProps) {
  const [audioStatus,  setAudioStatus]  = useState(block.audio_status ?? 'none');
  const [genAudio,     setGenAudio]     = useState(false);
  const [editing,      setEditing]      = useState(false);
  const [draft,        setDraft]        = useState(block.body || '');
  const [saving,       setSaving]       = useState(false);
  const audioUrl = `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/${block.id}/audio`;

  useEffect(() => {
    if (audioStatus !== 'generating') return;
    let alive = true;
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/content-blocks`,
          { headers: token ? { Authorization: `Bearer ${token}` } : {} });
        if (!res.ok || !alive) return;
        const blocks: ContentBlock[] = await res.json();
        const up = blocks.find(b => b.id === block.id);
        if (up && up.audio_status !== 'generating') { setAudioStatus(up.audio_status); clearInterval(iv); }
      } catch { /* ignore */ }
    }, 3000);
    return () => { alive = false; clearInterval(iv); };
  }, [audioStatus]);

  async function handleGenerateAudio() {
    if (!token) return;
    setGenAudio(true);
    try { await generateBlockAudio(conceptId, block.id, token); setAudioStatus('generating'); }
    catch { setAudioStatus('failed'); }
    finally { setGenAudio(false); }
  }

  async function handleSaveEdit() {
    if (!token) return;
    setSaving(true);
    try {
      await updateContentBlock(conceptId, block.id, { body: draft }, token);
      block.body = draft;
      setEditing(false);
    } catch { /* ignore */ } finally { setSaving(false); }
  }

  return (
    <div>
      {block.title && <h3 className="text-base font-semibold text-[var(--tx2)] mb-2">{block.title}</h3>}

      {editing ? (
        <div className="space-y-2">
          <textarea value={draft} onChange={e => setDraft(e.target.value)}
            rows={Math.max(6, draft.split('\n').length + 2)} autoFocus
            className="w-full text-sm bg-[var(--ov1)] border border-purple-500/40 rounded-xl px-3 py-2.5
                       text-[var(--tx2)] leading-relaxed resize-y focus:outline-none focus:ring-1
                       focus:ring-purple-500/50 font-mono" />
          <div className="flex gap-2">
            <button onClick={handleSaveEdit} disabled={saving}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-purple-600
                         hover:bg-purple-500 text-white font-medium disabled:opacity-50">
              {saving ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button onClick={() => { setEditing(false); setDraft(block.body || ''); }}
              className="text-xs px-3 py-1.5 rounded-lg border border-[var(--bd)] text-[var(--tx6)]
                         hover:text-[var(--tx2)] transition-colors">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="relative">
          {editable && (
            <button onClick={() => setEditing(true)} title="Edit text"
              className="absolute top-0 right-0 p-1 text-[var(--tx8)] hover:text-purple-400 transition-colors">
              <Pencil size={12} />
            </button>
          )}
          <div className="prose prose-sm max-w-none text-[var(--tx3)] pr-6
                          [&_p]:text-[var(--tx4)] [&_p]:leading-relaxed
                          [&_h1]:text-[var(--tx2)] [&_h2]:text-[var(--tx2)] [&_h3]:text-[var(--tx3)]
                          [&_strong]:text-[var(--tx2)] [&_li]:text-[var(--tx4)]
                          [&_code]:bg-[var(--bg3)] [&_code]:text-purple-300 [&_code]:px-1 [&_code]:rounded">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}>
              {preprocessMath(block.body || '')}
            </ReactMarkdown>
          </div>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-[var(--bd)]">
        {audioStatus === 'ready' ? (
          <div className="flex items-center gap-2">
            <audio controls src={audioUrl} className="flex-1 h-8" />
            {editable && (
              <button onClick={handleGenerateAudio} disabled={genAudio} title="Regenerate audio"
                className="text-[var(--tx8)] hover:text-purple-400 transition-colors shrink-0">
                <Mic2 size={13} />
              </button>
            )}
          </div>
        ) : audioStatus === 'generating' ? (
          <div className="flex items-center gap-2 text-xs text-[var(--tx7)]">
            <Loader2 size={12} className="animate-spin text-purple-400" /> Generating audio…
          </div>
        ) : editable ? (
          <button onClick={handleGenerateAudio} disabled={genAudio}
            className="flex items-center gap-1.5 text-xs text-[var(--tx8)] hover:text-purple-400 transition-colors">
            {genAudio ? <Loader2 size={12} className="animate-spin" /> : <Mic2 size={12} />}
            {audioStatus === 'failed' ? 'Retry audio' : 'Generate audio'}
          </button>
        ) : null}
      </div>
    </div>
  );
}

// ── Sortable row ──────────────────────────────────────────────────────────────

interface SortableBlockProps {
  block: ContentBlock; conceptId: string; token?: string; editable?: boolean;
  onDelete: (id: string) => void;
  onLightbox: (url: string) => void;
  onPdf: (url: string, title: string) => void;
}

function SortableBlock({ block, conceptId, token, editable, onDelete, onLightbox, onPdf }: SortableBlockProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };

  return (
    <div ref={setNodeRef} style={style} className="flex items-start gap-2">
      {editable && (
        <div className="flex flex-col items-center gap-1 pt-2 shrink-0">
          <div {...attributes} {...listeners}
            className="cursor-grab active:cursor-grabbing text-[var(--tx7)] hover:text-[var(--tx3)]
                       transition-colors p-1 touch-none" title="Drag to reorder">
            <GripVertical size={15} />
          </div>
          <button onClick={() => onDelete(block.id)}
            className="text-[var(--tx8)] hover:text-red-400 transition-colors p-1" title="Delete block">
            <Trash2 size={13} />
          </button>
        </div>
      )}
      <div className="flex-1 min-w-0">
        {block.type === 'video'       ? <VideoBlock      block={block} token={token} />
        : block.type === 'audio'      ? <AudioBlock      block={block} />
        : block.type === 'embed_video'? <EmbedVideoBlock block={block} />
        : block.type === 'embed_image'? <EmbedImageBlock block={block} onLightbox={onLightbox} />
        : block.type === 'embed_pdf'  ? <EmbedPdfBlock   block={block} onOpen={onPdf} />
        : <TextBlock block={block} conceptId={conceptId} token={token} editable={editable} />}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface ConceptTextbookProps {
  conceptId: string; token: string; editable?: boolean;
  onHasBlocks?: (has: boolean) => void;
}

export function ConceptTextbook({ conceptId, token, editable = false, onHasBlocks }: ConceptTextbookProps) {
  const [blocks,       setBlocks]       = useState<ContentBlock[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState<string | null>(null);
  const [dirty,        setDirty]        = useState(false);
  const [saving,       setSaving]       = useState(false);
  const [saved,        setSaved]        = useState(false);
  const [lightboxUrl,  setLightboxUrl]  = useState<string | null>(null);
  const [pdfModal,     setPdfModal]     = useState<{ url: string; title: string } | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const load = useCallback(() => {
    if (!conceptId) return;
    setLoading(true); setError(null);
    listContentBlocks(conceptId, token)
      .then(data => { setBlocks(data); onHasBlocks?.(data.length > 0); setDirty(false); })
      .catch(e => setError(e.message ?? 'Failed to load'))
      .finally(() => setLoading(false));
  }, [conceptId, token]);

  useEffect(() => { load(); }, [load]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setBlocks(prev => arrayMove(prev, prev.findIndex(b => b.id === active.id), prev.findIndex(b => b.id === over.id)));
    setDirty(true); setSaved(false);
  }

  async function saveOrder() {
    setSaving(true);
    try {
      await reorderContentBlocks(conceptId, blocks.map((b, i) => ({ id: b.id, position: i })), token);
      setDirty(false); setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch { /* leave dirty */ } finally { setSaving(false); }
  }

  async function handleDelete(blockId: string) {
    try {
      await deleteContentBlock(conceptId, blockId, token);
      setBlocks(prev => { const n = prev.filter(b => b.id !== blockId); onHasBlocks?.(n.length > 0); return n; });
    } catch (e: any) { alert('Delete failed: ' + e.message); }
  }

  if (loading) return <div className="flex justify-center py-8"><Loader2 size={18} className="animate-spin text-purple-400" /></div>;
  if (error)   return <div className="flex items-center gap-2 py-4 text-red-400 text-sm">
    <span>Failed to load: {error}</span>
    <button onClick={load} className="underline text-xs">Retry</button>
  </div>;
  if (blocks.length === 0) return editable
    ? <p className="text-[var(--tx7)] text-sm py-4">No content blocks yet. Use Studio to draft content and add it here.</p>
    : null;

  const blockList = (
    <div className="space-y-6">
      {blocks.map(block => (
        editable
          ? <SortableBlock key={block.id} block={block} conceptId={conceptId} token={token}
              editable onDelete={handleDelete} onLightbox={setLightboxUrl}
              onPdf={(url, title) => setPdfModal({ url, title })} />
          : <div key={block.id}>
              {block.type === 'video'        ? <VideoBlock      block={block} token={token} />
              : block.type === 'audio'       ? <AudioBlock      block={block} />
              : block.type === 'embed_video' ? <EmbedVideoBlock block={block} />
              : block.type === 'embed_image' ? <EmbedImageBlock block={block} onLightbox={setLightboxUrl} />
              : block.type === 'embed_pdf'   ? <EmbedPdfBlock   block={block} onOpen={(u,t) => setPdfModal({url:u,title:t})} />
              : <TextBlock block={block} conceptId={conceptId} token={token} />}
            </div>
      ))}
    </div>
  );

  return (
    <div>
      {/* Save-order bar */}
      {editable && (dirty || saved) && (
        <div className="flex items-center justify-between mb-4 px-3 py-2 rounded-xl border border-[var(--bd)] bg-[var(--ov1)]">
          <span className="text-xs text-[var(--tx6)]">
            {saved ? 'Order saved' : 'Unsaved order — save when done'}
          </span>
          <button onClick={saveOrder} disabled={saving || !dirty}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-purple-600
                       hover:bg-purple-500 text-white font-medium disabled:opacity-50">
            {saving ? <Loader2 size={11} className="animate-spin" /> : saved ? <Check size={11} /> : <Save size={11} />}
            {saving ? 'Saving…' : saved ? 'Saved!' : 'Save order'}
          </button>
        </div>
      )}

      {editable ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={blocks.map(b => b.id)} strategy={verticalListSortingStrategy}>
            {blockList}
          </SortableContext>
        </DndContext>
      ) : blockList}

      {/* Image lightbox */}
      {lightboxUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setLightboxUrl(null)}>
          <div className="relative max-w-[92vw] max-h-[92vh]" onClick={e => e.stopPropagation()}>
            <button onClick={() => setLightboxUrl(null)}
              className="absolute -top-9 right-0 text-white/60 hover:text-white p-1 transition-colors">
              <X size={18} />
            </button>
            <img src={lightboxUrl} alt="Full size" className="max-w-[92vw] max-h-[92vh] rounded-xl object-contain shadow-2xl" />
          </div>
        </div>
      )}

      {/* PDF modal */}
      {pdfModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPdfModal(null)}>
          <div className="relative w-[90vw] h-[90vh] flex flex-col rounded-xl overflow-hidden shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--surface)] border-b border-[var(--bd)]">
              <div className="flex items-center gap-2">
                <FileText size={14} className="text-red-400" />
                <span className="text-sm font-medium text-[var(--tx2)]">{pdfModal.title}</span>
              </div>
              <div className="flex items-center gap-2">
                <a href={pdfModal.url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-[var(--tx6)] hover:text-purple-400 transition-colors">
                  <ExternalLink size={11} /> Open in tab
                </a>
                <button onClick={() => setPdfModal(null)}
                  className="text-[var(--tx7)] hover:text-[var(--tx2)] transition-colors p-1">
                  <X size={16} />
                </button>
              </div>
            </div>
            <iframe src={pdfModal.url} className="flex-1 w-full bg-white" title={pdfModal.title} />
          </div>
        </div>
      )}
    </div>
  );
}
