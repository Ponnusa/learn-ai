'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Sparkles, Loader2, Download, RefreshCw,
  ZoomIn, X, Clock, MessageSquare, Trash2, FileText, AlertCircle,
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useSessionStore } from '@/store/sessionStore';
import { generateEduImage, getEduImageJob, listEduImages, deleteEduImage, retryEduImage, EduImageJob } from '@/lib/api';

// ── Domain styles (gradient bg + badge color) — mirrors video SUBJECT_STYLES ──

const DOMAIN_STYLES: Record<string, { badge: string; gradient: string }> = {
  physics:     { badge: 'bg-blue-500/15 text-blue-400 border-blue-500/20',     gradient: 'from-blue-950 via-cyan-950 to-slate-900' },
  chemistry:   { badge: 'bg-green-500/15 text-green-400 border-green-500/20',  gradient: 'from-emerald-950 via-teal-950 to-slate-900' },
  mathematics: { badge: 'bg-purple-500/15 text-purple-400 border-purple-500/20', gradient: 'from-purple-950 via-indigo-950 to-slate-900' },
  biology:     { badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', gradient: 'from-emerald-950 via-green-950 to-slate-900' },
  geography:   { badge: 'bg-amber-500/15 text-amber-400 border-amber-500/20',  gradient: 'from-amber-950 via-yellow-950 to-slate-900' },
  general:     { badge: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/20', gradient: 'from-indigo-950 via-slate-900 to-zinc-900' },
};
const DEFAULT_DOMAIN_STYLE = { badge: 'bg-[var(--ov3)] text-[var(--tx5)] border-[var(--bd)]', gradient: 'from-gray-900 via-slate-900 to-zinc-900' };
function domainStyle(d?: string) { return DOMAIN_STYLES[(d || '').toLowerCase()] ?? DEFAULT_DOMAIN_STYLE; }

function DomainBadge({ domain }: { domain?: string }) {
  if (!domain) return null;
  const { badge } = domainStyle(domain);
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize border shrink-0 ${badge}`}>
      {domain}
    </span>
  );
}

function formatDate(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7)  return `${diff}d ago`;
  return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

const EXAMPLES = [
  'Forces acting on a sled moving down an inclined plane',
  'Water cycle — evaporation, condensation, and precipitation',
  'Structure of a human neuron',
  "Newton's Third Law — action and reaction forces",
  'Photosynthesis process in a plant cell',
  'Structure of a DNA double helix',
  'Phases of mitosis',
  'Covalent bonding in a water molecule',
  'Projectile motion parabola',
  'The rock cycle',
];


// ── ImageLightbox ─────────────────────────────────────────────────────────────

function ImageLightbox({ src, title, description, onClose }: { src: string; title: string; description?: string; onClose: () => void }) {
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === '+' || e.key === '=') setZoom(z => Math.min(4, z + 0.3));
      if (e.key === '-') setZoom(z => Math.max(0.5, z - 0.3));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}>
      <div className="absolute top-4 right-4 flex items-center gap-1.5">
        <button onClick={e => { e.stopPropagation(); setZoom(z => Math.max(0.5, z - 0.3)); }}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <span className="text-sm font-bold">−</span>
        </button>
        <span className="text-white/40 text-xs w-10 text-center">{Math.round(zoom * 100)}%</span>
        <button onClick={e => { e.stopPropagation(); setZoom(z => Math.min(4, z + 0.3)); }}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <span className="text-sm font-bold">+</span>
        </button>
        <a href={src} download="educational-diagram.png"
          onClick={e => e.stopPropagation()}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <Download size={15} />
        </a>
        <button onClick={onClose}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <X size={15} />
        </button>
      </div>
      <div className="flex flex-col items-center gap-4 max-w-3xl w-full" onClick={e => e.stopPropagation()}>
        <img src={src} alt={title}
          style={{ transform: `scale(${zoom})`, transition: 'transform 0.15s ease', transformOrigin: 'center' }}
          className="max-w-full max-h-[70vh] object-contain rounded-xl select-none cursor-zoom-in bg-white"
          onClick={() => setZoom(z => z === 1 ? 2 : 1)}
          draggable={false}
        />
        {description && (
          <div className="w-full bg-white/5 border border-white/10 rounded-xl px-5 py-4 text-left">
            <p className="text-white/50 text-[10px] uppercase tracking-wide font-medium mb-2">About this diagram</p>
            <p className="text-white/75 text-sm leading-relaxed whitespace-pre-wrap">{description}</p>
          </div>
        )}
        <p className="text-white/20 text-xs">Click image to toggle zoom · Esc to close</p>
      </div>
    </div>
  );
}

// ── ImageCard — matches VideoLibraryCard structure ────────────────────────────

function ImageCard({ job, onClick, onGoToChat, onRemove }: {
  job: EduImageJob;
  onClick: () => void;
  onGoToChat?: () => void;
  onRemove?: (id: string) => void;
}) {
  const { token } = useSessionStore();
  const { badge, gradient } = domainStyle(job.domain);
  const date     = job.created_at ? formatDate(job.created_at) : '';
  const score    = job.critic_report?.score;
  const scoreColor = score == null ? '' : score >= 85 ? 'bg-emerald-500/80' : score >= 70 ? 'bg-amber-500/80' : 'bg-red-500/80';

  const [deleting, setDeleting] = useState(false);
  const [retrying, setRetrying] = useState(false);

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (!job.id) return;
    setDeleting(true);
    try { await deleteEduImage(job.id, token ?? undefined); onRemove?.(job.id); }
    catch { setDeleting(false); }
  }

  async function handleRetry(e: React.MouseEvent) {
    e.stopPropagation();
    if (!job.id) return;
    setRetrying(true);
    try { await retryEduImage(job.id, token ?? undefined); }
    catch {}
    finally { setRetrying(false); }
  }

  return (
    <div
      onClick={job.status === 'ready' ? onClick : undefined}
      className={`group bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden
                  transition-all duration-200 flex flex-col
                  ${job.status === 'ready'
                    ? 'cursor-pointer hover:border-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/8'
                    : ''}`}
    >
      {/* ── Thumbnail ── */}
      <div className={`aspect-video relative overflow-hidden bg-gradient-to-br ${gradient} shrink-0`}>
        {job.image_url ? (
          <img src={job.image_url} alt={job.concept}
            className="w-full h-full object-contain bg-white" />
        ) : job.status === 'processing' ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <Loader2 size={28} className="text-white/40 animate-spin" />
            <p className="text-white/30 text-[10px]">Generating…</p>
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <AlertCircle size={24} className="text-red-400/60" />
            <p className="text-white/30 text-[10px]">Failed</p>
          </div>
        )}

        {/* Zoom overlay on hover (ready only) */}
        {job.status === 'ready' && (
          <div className="absolute inset-0 flex items-center justify-center
                          opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full
                            flex items-center justify-center ring-1 ring-white/30">
              <ZoomIn size={20} className="text-white" />
            </div>
          </div>
        )}

        {/* Quality score pill (bottom-right) — like duration pill on videos */}
        {score != null && (
          <div className={`absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-white text-[10px]
                           font-semibold leading-none ${scoreColor} backdrop-blur-sm`}>
            {score}/100
          </div>
        )}
      </div>

      {/* ── Card body ── */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        {/* Title */}
        <p className="text-[var(--tx1)] text-sm font-medium line-clamp-2 leading-snug min-h-[2.5rem]">
          {job.concept}
        </p>

        {/* Footer row: badge + date | action buttons */}
        <div className="flex items-center justify-between gap-1 mt-auto">
          <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
            {job.domain && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize
                               border shrink-0 ${badge}`}>
                {job.domain}
              </span>
            )}
            {date && <span className="text-[var(--tx6)] text-xs truncate">{date}</span>}
          </div>

          <div className="flex items-center gap-0.5 shrink-0">
            {/* Description (if available) */}
            {job.description && (
              <button
                onClick={e => { e.stopPropagation(); onClick(); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                title="View description"
              >
                <FileText size={13} />
              </button>
            )}
            {/* Go to chat */}
            {onGoToChat && job.status === 'ready' && (
              <button
                onClick={e => { e.stopPropagation(); onGoToChat(); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
                title="Go to chat message"
              >
                <MessageSquare size={13} />
              </button>
            )}
            {/* Retry (failed) */}
            {job.status === 'failed' && (
              <button
                onClick={handleRetry}
                disabled={retrying}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                title="Retry"
              >
                <RefreshCw size={13} className={retrying ? 'animate-spin' : ''} />
              </button>
            )}
            {/* Delete */}
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="w-7 h-7 flex items-center justify-center rounded-lg
                         text-[var(--tx5)] hover:text-red-400 hover:bg-red-500/10 transition-colors"
              title="Delete"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ImagesPage() {
  const router             = useRouter();
  const { user, token, sessionId } = useSessionStore();
  const [concept, setConcept]   = useState('');
  const [jobId,   setJobId]     = useState<string | null>(null);
  const [current, setCurrent]   = useState<EduImageJob | null>(null);
  const [history, setHistory]   = useState<EduImageJob[]>([]);
  const [histLoading, setHistLoading] = useState(false);
  const [lightbox, setLightbox] = useState<EduImageJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load history
  useEffect(() => {
    setHistLoading(true);
    listEduImages({ user_id: user?.id, session_id: sessionId ?? undefined }, token ?? undefined)
      .then(r => { setHistory(r); setHistLoading(false); })
      .catch(() => setHistLoading(false));
  }, [user?.id, sessionId]);

  // Poll active job
  useEffect(() => {
    if (!jobId) return;
    function poll() {
      getEduImageJob(jobId!, token ?? undefined).then(job => {
        setCurrent(job);
        if (job.status === 'processing') {
          pollRef.current = setTimeout(poll, 3000);
        } else {
          setJobId(null);
          setHistory(prev => [job, ...prev.filter(h => h.id !== job.id)]);
        }
      }).catch(() => { pollRef.current = setTimeout(poll, 5000); });
    }
    poll();
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, [jobId]);

  async function handleGenerate() {
    const c = concept.trim(); if (!c) return;
    setCurrent({ concept: c, status: 'processing' });
    setHistory(prev => [{ concept: c, status: 'processing' }, ...prev]);
    try {
      const res = await generateEduImage({ concept: c, user_id: user?.id, session_id: sessionId ?? undefined }, token ?? undefined);
      setJobId(res.jobId);
      setConcept('');
    } catch (e: any) {
      const isLimit = e?.message === 'session_limit_reached' || e?.message === 'Daily image limit reached';
      if (isLimit) {
        setCurrent({ concept: c, status: 'failed', error_msg: '⚠️ Daily diagram limit reached. Come back tomorrow or upgrade your plan.' });
        setHistory(prev => prev.filter(h => h.concept !== c || h.status !== 'processing'));
      } else {
        setCurrent({ concept: c, status: 'failed', error_msg: e.message });
      }
    }
  }

  const isGenerating = current?.status === 'processing';

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 sm:px-6 py-4 border-b border-[var(--bd)] shrink-0">
          <div className="flex-1 min-w-0">
            <h1 className="text-[var(--tx1)] font-semibold">Educational Diagrams</h1>
            <p className="text-[var(--tx6)] text-xs mt-0.5">Generate textbook-quality illustrations from any concept</p>
          </div>
        </div>

        <div className="flex-1 chat-scroll">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-8">

            {/* ── Generator input ─────────────────────────────────── */}
            <div className="space-y-3">
              <div className="relative">
                <textarea
                  ref={inputRef}
                  value={concept}
                  onChange={e => setConcept(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleGenerate(); } }}
                  placeholder="Describe an educational concept to visualise…"
                  rows={2}
                  disabled={isGenerating}
                  className="w-full px-4 py-3.5 pr-24 rounded-2xl bg-[var(--surface)] border border-[var(--bd)]
                             text-[var(--tx1)] text-sm placeholder-[var(--tx7)] resize-none
                             focus:outline-none focus:border-indigo-500/50 disabled:opacity-60 transition-colors
                             leading-relaxed"
                />
                <button
                  onClick={handleGenerate}
                  disabled={!concept.trim() || isGenerating}
                  className="absolute right-3 bottom-3 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold
                             bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white transition-colors">
                  {isGenerating ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  {isGenerating ? 'Generating…' : 'Generate'}
                </button>
              </div>

              {/* Example pills */}
              <div className="flex flex-wrap gap-1.5">
                {EXAMPLES.slice(0, 5).map(ex => (
                  <button key={ex} onClick={() => { setConcept(ex); inputRef.current?.focus(); }}
                    className="text-[10px] px-2.5 py-1 rounded-full bg-[var(--ov3)] hover:bg-[var(--ov4)]
                               text-[var(--tx5)] hover:text-[var(--tx2)] border border-[var(--bd)]
                               transition-colors truncate max-w-[180px]">
                    {ex}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Current / latest result ──────────────────────────── */}
            {current && (
              <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] overflow-hidden">
                {/* Status bar */}
                <div className="flex items-center gap-3 px-5 py-3 border-b border-[var(--bd)]">
                  <DomainBadge domain={current.domain} />
                  <p className="text-[var(--tx3)] text-sm flex-1 truncate">{current.concept}</p>
                  {current.status === 'processing' && (
                    <span className="text-[11px] text-yellow-400 flex items-center gap-1.5 shrink-0">
                      <Loader2 size={11} className="animate-spin" /> Processing…
                    </span>
                  )}
                  {current.status === 'ready' && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <a href={current.image_url!} download="educational-diagram.png"
                        className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg
                                   bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx4)]
                                   border border-[var(--bd)] transition-colors">
                        <Download size={11} /> Save
                      </a>
                      <button onClick={() => { setConcept(current.concept); inputRef.current?.focus(); }}
                        className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg
                                   bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx4)]
                                   border border-[var(--bd)] transition-colors">
                        <RefreshCw size={11} /> Re-generate
                      </button>
                    </div>
                  )}
                </div>

                {/* Image or loading state */}
                {current.status === 'processing' ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-4">
                    <div className="relative w-16 h-16">
                      <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20" />
                      <div className="absolute inset-0 rounded-full border-2 border-t-indigo-500 animate-spin" />
                      <div className="absolute inset-2 rounded-full bg-indigo-500/10 flex items-center justify-center">
                        <Sparkles size={16} className="text-indigo-400" />
                      </div>
                    </div>
                    <div className="text-center">
                      <p className="text-[var(--tx3)] text-sm font-medium">Creating your diagram…</p>
                      <p className="text-[var(--tx6)] text-xs mt-1">Knowledge extraction → Diagram plan → gpt-image-1 → Quality review</p>
                    </div>
                  </div>
                ) : current.status === 'ready' && current.image_url ? (
                  <button className="block w-full group relative" onClick={() => setLightbox(current)}>
                    <img src={current.image_url} alt={current.concept}
                      className="w-full object-contain bg-white max-h-[520px]" />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors
                                    flex items-center justify-center opacity-0 group-hover:opacity-100">
                      <div className="bg-black/60 rounded-full p-3">
                        <ZoomIn size={20} className="text-white" />
                      </div>
                    </div>
                  </button>
                ) : current.status === 'failed' ? (
                  <div className="flex flex-col items-center justify-center py-12 gap-3">
                    <p className="text-red-400 text-sm">Generation failed</p>
                    <p className="text-[var(--tx6)] text-xs max-w-sm text-center">{current.error_msg}</p>
                    <button onClick={() => { setConcept(current.concept); handleGenerate(); }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium
                                 bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx3)] border border-[var(--bd)] transition-colors">
                      <RefreshCw size={11} /> Try again
                    </button>
                  </div>
                ) : null}

                {/* AI description — the explanation that used to live inside the image */}
                {current.status === 'ready' && current.description && (
                  <div className="px-5 py-4 border-t border-[var(--bd)] bg-[var(--surface)]">
                    <p className="text-[var(--tx6)] text-[10px] uppercase tracking-wide font-medium mb-2">About this diagram</p>
                    <div className="text-[var(--tx3)] text-sm leading-relaxed space-y-2 whitespace-pre-wrap">
                      {current.description}
                    </div>
                  </div>
                )}

                {/* Knowledge layer detail */}
                {current.status === 'ready' && (
                  <div className="px-5 py-3 border-t border-[var(--bd)] bg-[var(--ov2)] space-y-2.5">
                    {/* Learning goal */}
                    {current.knowledge_model?.learning_goal && (
                      <p className="text-[var(--tx5)] text-xs leading-snug">
                        <span className="text-[var(--tx7)] font-medium">Goal: </span>
                        {current.knowledge_model.learning_goal}
                      </p>
                    )}
                    {/* Visual elements */}
                    {(current.spec?.visual_elements ?? current.knowledge_model?.must_show ?? []).length > 0 && (
                      <div>
                        <p className="text-[var(--tx7)] text-[10px] uppercase tracking-wide font-medium mb-1">Shows</p>
                        <div className="flex flex-wrap gap-1.5">
                          {(current.spec?.visual_elements ?? current.knowledge_model?.must_show ?? []).map((el: string) => (
                            <span key={el} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--surface)]
                                                       border border-[var(--bd)] text-[var(--tx5)]">
                              {el}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {/* Critic score */}
                    {current.critic_report?.score != null && (
                      <div className="flex items-center gap-2">
                        <span className="text-[var(--tx7)] text-[10px] uppercase tracking-wide font-medium">Quality score</span>
                        <span className={`text-xs font-semibold ${
                          (current.critic_report.score ?? 0) >= 85 ? 'text-emerald-400' :
                          (current.critic_report.score ?? 0) >= 70 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {current.critic_report.score}/100
                        </span>
                        {(current.generation_attempts ?? 1) > 1 && (
                          <span className="text-[var(--tx8)] text-[10px]">
                            ({current.generation_attempts} attempts)
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── Past images gallery ──────────────────────────────── */}
            {(history.length > 0 || histLoading) && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Clock size={13} className="text-[var(--tx6)]" />
                  <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">
                    Past diagrams
                  </p>
                </div>
                {histLoading ? (
                  <div className="flex items-center justify-center py-8 gap-2 text-[var(--tx6)] text-sm">
                    <Loader2 size={14} className="animate-spin" /> Loading…
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {history.map((job, i) => (
                      <ImageCard
                        key={job.id ?? job.jobId ?? i}
                        job={job}
                        onClick={() => job.image_url ? setLightbox(job) : undefined}
                        onGoToChat={job.conversation_id
                          ? () => router.push(`/?conv=${job.conversation_id}${job.message_id ? `&msg=${job.message_id}` : ''}`)
                          : undefined
                        }
                        onRemove={id => setHistory(prev => prev.filter(h => h.id !== id))}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Empty state */}
            {!current && history.length === 0 && !histLoading && (
              <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20
                                flex items-center justify-center">
                  <Sparkles size={28} className="text-indigo-400" />
                </div>
                <div>
                  <p className="text-[var(--tx2)] font-medium">Generate your first diagram</p>
                  <p className="text-[var(--tx6)] text-sm mt-1 max-w-xs">
                    Describe any educational concept — physics, chemistry, biology, geography, and more.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 justify-center max-w-md">
                  {EXAMPLES.slice(5).map(ex => (
                    <button key={ex} onClick={() => { setConcept(ex); inputRef.current?.focus(); }}
                      className="text-[11px] px-3 py-1.5 rounded-xl bg-[var(--surface)] hover:bg-[var(--ov3)]
                                 text-[var(--tx4)] border border-[var(--bd)] transition-colors">
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      </main>

      {lightbox && (
        <ImageLightbox
          src={lightbox.image_url!}
          title={lightbox.concept}
          description={lightbox.description}
          onClose={() => setLightbox(null)}
        />
      )}
    </div>
  );
}
