'use client';
import { useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Loader2, Video, Volume2, Trash2, Mic2 } from 'lucide-react';
import { ContentBlock, listContentBlocks, deleteContentBlock, generateBlockAudio } from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden">
      {block.title && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
          <span className="text-sm font-medium text-[var(--tx2)] flex items-center gap-2">
            <Video size={14} className="text-purple-400" /> {block.title}
          </span>
          {onDelete && (
            <button onClick={onDelete} className="text-[var(--tx8)] hover:text-red-400 transition-colors p-0.5">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      )}
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
    <div className="rounded-xl border border-[var(--bd)] overflow-hidden">
      {block.title && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--bd)] bg-[var(--bg2)]">
          <span className="text-sm font-medium text-[var(--tx2)] flex items-center gap-2">
            <Volume2 size={14} className="text-blue-400" /> {block.title}
          </span>
          {onDelete && (
            <button onClick={onDelete} className="text-[var(--tx8)] hover:text-red-400 transition-colors p-0.5">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      )}
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

  // Poll while generating
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
    } catch { /* ignore */ } finally {
      setGeneratingAudio(false);
    }
  }

  return (
    <div className="relative group">
      {block.title && (
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold text-[var(--tx2)]">{block.title}</h3>
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

      {/* Audio strip */}
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

      {!editable && onDelete === undefined && (
        /* Delete button for teacher when no title (title row already has it) */
        null
      )}
    </div>
  );
}

interface ConceptTextbookProps {
  conceptId:    string;
  token:        string;
  editable?:    boolean;
  onHasBlocks?: (has: boolean) => void;
}

export function ConceptTextbook({ conceptId, token, editable = false, onHasBlocks }: ConceptTextbookProps) {
  const [blocks,  setBlocks]  = useState<ContentBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  const load = useCallback(() => {
    if (!conceptId) return;
    setLoading(true);
    setError(null);
    listContentBlocks(conceptId, token)
      .then(data => {
        setBlocks(data);
        onHasBlocks?.(data.length > 0);
      })
      .catch(e => setError(e.message ?? 'Failed to load'))
      .finally(() => setLoading(false));
  }, [conceptId, token]);

  useEffect(() => { load(); }, [load]);

  async function handleDelete(blockId: string) {
    try {
      await deleteContentBlock(conceptId, blockId, token);
      setBlocks(prev => prev.filter(b => b.id !== blockId));
    } catch (e: any) {
      alert('Delete failed: ' + e.message);
    }
  }

  if (loading) return <div className="flex justify-center py-8"><Loader2 size={18} className="animate-spin text-purple-400" /></div>;

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
    <div className="space-y-6">
      {blocks.map(block => (
        <div key={block.id}>
          {block.type === 'video' ? (
            <VideoBlock
              block={block} token={token}
              onDelete={editable ? () => handleDelete(block.id) : undefined}
            />
          ) : block.type === 'audio' ? (
            <AudioBlock
              block={block}
              onDelete={editable ? () => handleDelete(block.id) : undefined}
            />
          ) : (
            <TextBlock
              block={block}
              conceptId={conceptId}
              token={token}
              editable={editable}
              onDelete={editable ? () => handleDelete(block.id) : undefined}
              onAudioGenerated={() => {/* status already updated inside TextBlock */}}
            />
          )}
        </div>
      ))}
    </div>
  );
}
