'use client';
import { useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Loader2, Video, Volume2, Trash2, Mic2, GripVertical, Save, Check } from 'lucide-react';
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { ContentBlock, listContentBlocks, deleteContentBlock, generateBlockAudio, reorderContentBlocks } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Sub-block renderers ───────────────────────────────────────────────────────

function VideoBlock({ block, token, onDelete }: { block: ContentBlock; token?: string; onDelete?: () => void }) {
  const [videoUrl, setVideoUrl] = useState(block.video_url);
  const [status,   setStatus]   = useState(block.video_status);
  const [polling,  setPolling]  = useState(!block.video_url && !!block.video_id);

  useEffect(() => {
    if (!polling || !block.video_id) return;
    let active = true;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/videos/${block.video_id}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!active) return;
        setStatus(data.status);
        if (data.url) { setVideoUrl(data.url); setPolling(false); }
        if (data.status === 'failed') setPolling(false);
      } catch { /* ignore */ }
    }, 5000);
    return () => { active = false; clearInterval(interval); };
  }, [polling, block.video_id, token]);

  return (
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden group">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
        <span className="text-sm font-medium text-[var(--tx2)] flex items-center gap-2">
          <Video size={14} className="text-purple-400" /> {block.title || 'Video'}
        </span>
        {onDelete && (
          <button onClick={onDelete}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--tx8)] hover:text-red-400 p-0.5">
            <Trash2 size={13} />
          </button>
        )}
      </div>
      {videoUrl ? (
        <video src={videoUrl} controls className="w-full aspect-video bg-black" preload="metadata" />
      ) : (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-[var(--tx7)]">
          {status === 'failed' ? (
            <p className="text-sm text-red-400">Video generation failed</p>
          ) : (
            <>
              <Loader2 size={20} className="animate-spin text-purple-400" />
              <p className="text-xs">{
                status === 'transcript_ready' ? 'Writing animation code…' :
                status === 'queued'           ? 'Rendering video…' :
                status === 'rendering'        ? 'Rendering video…' :
                'Generating video…'
              }</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function AudioBlock({ block, onDelete }: { block: ContentBlock; onDelete?: () => void }) {
  return (
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden group">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
        <span className="text-sm font-medium text-[var(--tx2)] flex items-center gap-2">
          <Volume2 size={14} className="text-blue-400" /> {block.title || 'Audio'}
        </span>
        {onDelete && (
          <button onClick={onDelete}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--tx8)] hover:text-red-400 p-0.5">
            <Trash2 size={13} />
          </button>
        )}
      </div>
      <div className="px-4 py-3">
        <audio controls src={block.body || ''} className="w-full" />
      </div>
    </div>
  );
}

interface TextBlockProps {
  block:             ContentBlock;
  conceptId:         string;
  token?:            string;
  editable?:         boolean;
  onDelete?:         () => void;
  onAudioGenerated?: (blockId: string) => void;
}

function TextBlock({ block, conceptId, token, editable, onDelete, onAudioGenerated }: TextBlockProps) {
  const [audioStatus,     setAudioStatus]     = useState(block.audio_status ?? 'none');
  const [generatingAudio, setGeneratingAudio] = useState(false);
  const audioUrl = `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks/${block.id}/audio`;

  useEffect(() => {
    if (audioStatus !== 'generating') return;
    let active = true;
    const iv = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/courses/concepts/${conceptId}/content-blocks`,
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        if (!res.ok || !active) return;
        const blocks: ContentBlock[] = await res.json();
        const updated = blocks.find(b => b.id === block.id);
        if (updated && updated.audio_status !== 'generating') {
          setAudioStatus(updated.audio_status);
          if (updated.audio_status === 'ready') onAudioGenerated?.(block.id);
          clearInterval(iv);
        }
      } catch { /* ignore */ }
    }, 3000);
    return () => { active = false; clearInterval(iv); };
  }, [audioStatus]);

  async function handleGenerateAudio() {
    if (!token) return;
    setGeneratingAudio(true);
    try {
      await generateBlockAudio(conceptId, block.id, token);
      setAudioStatus('generating');
    } catch {
      setAudioStatus('failed');
    } finally {
      setGeneratingAudio(false);
    }
  }

  return (
    <div className="relative group">
      {(block.title || onDelete) && (
        <div className="flex items-center justify-between mb-2">
          {block.title
            ? <h3 className="text-base font-semibold text-[var(--tx2)]">{block.title}</h3>
            : <span />}
          {onDelete && (
            <button onClick={onDelete}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--tx8)] hover:text-red-400">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      )}
      <div className="prose prose-sm max-w-none text-[var(--tx3)]
                      [&_p]:text-[var(--tx4)] [&_p]:leading-relaxed
                      [&_h1]:text-[var(--tx2)] [&_h2]:text-[var(--tx2)] [&_h3]:text-[var(--tx3)]
                      [&_strong]:text-[var(--tx2)] [&_li]:text-[var(--tx4)]
                      [&_code]:bg-[var(--bg3)] [&_code]:text-purple-300 [&_code]:px-1 [&_code]:rounded">
        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
          {block.body || ''}
        </ReactMarkdown>
      </div>

      <div className="mt-3 pt-3 border-t border-[var(--bd)]">
        {audioStatus === 'ready' ? (
          <div className="flex items-center gap-2">
            <audio controls src={audioUrl} className="flex-1 h-8" />
            {editable && (
              <button onClick={handleGenerateAudio} disabled={generatingAudio}
                title="Regenerate audio"
                className="text-xs text-[var(--tx8)] hover:text-purple-400 transition-colors shrink-0">
                <Mic2 size={13} />
              </button>
            )}
          </div>
        ) : audioStatus === 'generating' ? (
          <div className="flex items-center gap-2 text-xs text-[var(--tx7)]">
            <Loader2 size={12} className="animate-spin text-purple-400" /> Generating audio…
          </div>
        ) : editable ? (
          <button onClick={handleGenerateAudio} disabled={generatingAudio}
            className="flex items-center gap-1.5 text-xs text-[var(--tx8)] hover:text-purple-400 transition-colors">
            {generatingAudio
              ? <Loader2 size={12} className="animate-spin" />
              : <Mic2 size={12} />}
            {audioStatus === 'failed' ? 'Retry audio' : 'Generate audio'}
          </button>
        ) : null}
      </div>
    </div>
  );
}

// ── Sortable wrapper ──────────────────────────────────────────────────────────

interface SortableBlockProps {
  block:     ContentBlock;
  conceptId: string;
  token?:    string;
  editable?: boolean;
  onDelete:  (id: string) => void;
}

function SortableBlock({ block, conceptId, token, editable, onDelete }: SortableBlockProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: block.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
    zIndex:  isDragging ? 50 : 'auto',
  };

  return (
    <div ref={setNodeRef} style={style} className="relative">
      {editable && (
        <div
          {...attributes}
          {...listeners}
          className="absolute -left-6 top-1/2 -translate-y-1/2 cursor-grab active:cursor-grabbing
                     text-[var(--tx8)] hover:text-[var(--tx4)] opacity-0 group-hover/row:opacity-100
                     transition-opacity p-1 touch-none"
          title="Drag to reorder"
        >
          <GripVertical size={15} />
        </div>
      )}
      <div className="group/row">
        {block.type === 'video' ? (
          <VideoBlock
            block={block} token={token}
            onDelete={editable ? () => onDelete(block.id) : undefined}
          />
        ) : block.type === 'audio' ? (
          <AudioBlock
            block={block}
            onDelete={editable ? () => onDelete(block.id) : undefined}
          />
        ) : (
          <TextBlock
            block={block}
            conceptId={conceptId}
            token={token}
            editable={editable}
            onDelete={editable ? () => onDelete(block.id) : undefined}
            onAudioGenerated={() => {}}
          />
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface ConceptTextbookProps {
  conceptId:    string;
  token:        string;
  editable?:    boolean;
  onHasBlocks?: (has: boolean) => void;
}

export function ConceptTextbook({ conceptId, token, editable = false, onHasBlocks }: ConceptTextbookProps) {
  const [blocks,   setBlocks]   = useState<ContentBlock[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);
  const [dirty,    setDirty]    = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [saved,    setSaved]    = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const load = useCallback(() => {
    if (!conceptId) return;
    setLoading(true);
    setError(null);
    listContentBlocks(conceptId, token)
      .then(data => {
        setBlocks(data);
        onHasBlocks?.(data.length > 0);
        setDirty(false);
      })
      .catch(e => setError(e.message ?? 'Failed to load'))
      .finally(() => setLoading(false));
  }, [conceptId, token]);

  useEffect(() => { load(); }, [load]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setBlocks(prev => {
      const oldIdx = prev.findIndex(b => b.id === active.id);
      const newIdx = prev.findIndex(b => b.id === over.id);
      return arrayMove(prev, oldIdx, newIdx);
    });
    setDirty(true);
    setSaved(false);
  }

  async function saveOrder() {
    setSaving(true);
    try {
      await reorderContentBlocks(
        conceptId,
        blocks.map((b, i) => ({ id: b.id, position: i })),
        token,
      );
      setDirty(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      /* leave dirty so teacher can retry */
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(blockId: string) {
    try {
      await deleteContentBlock(conceptId, blockId, token);
      setBlocks(prev => {
        const next = prev.filter(b => b.id !== blockId);
        onHasBlocks?.(next.length > 0);
        return next;
      });
    } catch (e: any) {
      alert('Delete failed: ' + e.message);
    }
  }

  if (loading) return (
    <div className="flex justify-center py-8">
      <Loader2 size={18} className="animate-spin text-purple-400" />
    </div>
  );

  if (error) return (
    <div className="flex items-center gap-2 py-4 text-red-400 text-sm">
      <span>Failed to load blocks: {error}</span>
      <button onClick={load} className="underline text-xs">Retry</button>
    </div>
  );

  if (blocks.length === 0) {
    if (!editable) return null;
    return (
      <p className="text-[var(--tx7)] text-sm py-4">
        No content blocks yet. Use Studio to draft content and add it here.
      </p>
    );
  }

  return (
    <div>
      {/* Save order bar — only shown when teacher has reordered */}
      {editable && (dirty || saved) && (
        <div className="flex items-center justify-between mb-4 px-3 py-2 rounded-xl
                        border border-[var(--bd)] bg-[var(--ov1)]">
          <span className="text-xs text-[var(--tx6)]">
            {saved ? 'Order saved' : 'Drag blocks to reorder'}
          </span>
          <button
            onClick={saveOrder}
            disabled={saving || !dirty}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                       bg-purple-600 hover:bg-purple-500 text-white font-medium
                       transition-colors disabled:opacity-50"
          >
            {saving  ? <Loader2 size={11} className="animate-spin" /> :
             saved   ? <Check   size={11} /> :
             <Save   size={11} />}
            {saving ? 'Saving…' : saved ? 'Saved!' : 'Save order'}
          </button>
        </div>
      )}

      {/* Drag context — only active in editable mode */}
      {editable ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={blocks.map(b => b.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-6 pl-6">
              {blocks.map(block => (
                <SortableBlock
                  key={block.id}
                  block={block}
                  conceptId={conceptId}
                  token={token}
                  editable
                  onDelete={handleDelete}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <div className="space-y-6">
          {blocks.map(block => (
            <div key={block.id}>
              {block.type === 'video' ? (
                <VideoBlock block={block} token={token} />
              ) : block.type === 'audio' ? (
                <AudioBlock block={block} />
              ) : (
                <TextBlock block={block} conceptId={conceptId} token={token} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
