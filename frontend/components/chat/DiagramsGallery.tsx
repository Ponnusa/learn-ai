'use client';
import { useState, useEffect, useCallback } from 'react';
import { ImageIcon, RefreshCw, Trash2, X, ZoomIn, AlertCircle, Loader, Download, FileText, MessageSquare } from 'lucide-react';
import {
  listEduImages, deleteEduImage, retryEduImage, getEduImageJob,
  type EduImageJob,
} from '@/lib/api';

const DOMAIN_STYLES: Record<string, { badge: string; gradient: string }> = {
  physics:     { badge: 'bg-blue-500/15 text-blue-400 border-blue-500/25',     gradient: 'from-blue-950 via-cyan-950 to-slate-900' },
  chemistry:   { badge: 'bg-green-500/15 text-green-400 border-green-500/25',  gradient: 'from-emerald-950 via-teal-950 to-slate-900' },
  mathematics: { badge: 'bg-purple-500/15 text-purple-400 border-purple-500/25', gradient: 'from-purple-950 via-indigo-950 to-slate-900' },
  biology:     { badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25', gradient: 'from-emerald-950 via-green-950 to-slate-900' },
  geography:   { badge: 'bg-amber-500/15 text-amber-400 border-amber-500/25',  gradient: 'from-amber-950 via-yellow-950 to-slate-900' },
  general:     { badge: 'bg-[var(--ov3)] text-[var(--tx5)] border-[var(--bd)]', gradient: 'from-gray-900 via-slate-900 to-zinc-900' },
};
function domainStyle(d?: string) { return DOMAIN_STYLES[(d || '').toLowerCase()] ?? DOMAIN_STYLES.general; }

function formatDate(iso?: string): string {
  if (!iso) return '';
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7)  return `${diff}d ago`;
  return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

/* ── Single image card ─────────────────────────────────────────────────────── */
function ImageCard({
  job: initial,
  token,
  onRemove,
}: {
  job: EduImageJob;
  token?: string;
  onRemove: (id: string) => void;
}) {
  const [job,      setJob]      = useState<EduImageJob>(initial);
  const [lightbox, setLightbox] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Poll while processing
  useEffect(() => {
    if (job.status !== 'processing') return;
    let stopped = false;
    const poll = async () => {
      try {
        const d = await getEduImageJob(job.id!, token);
        if (!stopped) {
          setJob(d);
          if (d.status === 'processing') setTimeout(poll, 3000);
        }
      } catch { if (!stopped) setTimeout(poll, 6000); }
    };
    const t = setTimeout(poll, 3000);
    return () => { stopped = true; clearTimeout(t); };
  }, [job.id, job.status, token]);

  async function handleRetry() {
    setRetrying(true);
    setJob(j => ({ ...j, status: 'processing', image_url: undefined }));
    try { await retryEduImage(job.id!, token); } catch { setJob(j => ({ ...j, status: 'failed' })); }
    finally { setRetrying(false); }
  }

  async function handleDelete() {
    setDeleting(true);
    try { await deleteEduImage(job.id!, token); onRemove(job.id!); } catch { setDeleting(false); }
  }

  const { badge, gradient } = domainStyle(job.domain);
  const date  = formatDate(job.created_at);
  const score = job.critic_report?.score;
  const scoreColor = score == null ? '' : score >= 85 ? 'bg-emerald-500/80' : score >= 70 ? 'bg-amber-500/80' : 'bg-red-500/80';

  return (
    <>
      <div
        onClick={job.status === 'ready' && job.image_url ? () => setLightbox(true) : undefined}
        className={`group bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden
                    flex flex-col transition-all duration-200
                    ${job.status === 'ready' ? 'cursor-pointer hover:border-teal-500/35 hover:shadow-lg hover:shadow-teal-500/8' : ''}`}
      >
        {/* Thumbnail */}
        <div className={`aspect-square relative overflow-hidden bg-gradient-to-br ${gradient} shrink-0`}>
          {job.status === 'ready' && job.image_url ? (
            <img src={job.image_url} alt={job.concept}
              className="w-full h-full object-contain bg-white" />
          ) : job.status === 'processing' ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
              <Loader size={22} className="animate-spin text-white/40" />
              <span className="text-white/30 text-[10px]">Generating…</span>
            </div>
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
              <AlertCircle size={22} className="text-red-400/60" />
              <span className="text-white/30 text-[10px]">Failed</span>
            </div>
          )}

          {/* Hover overlay */}
          {job.status === 'ready' && (
            <div className="absolute inset-0 flex items-center justify-center
                            opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
              <div className="w-9 h-9 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center ring-1 ring-white/30">
                <ZoomIn size={16} className="text-white" />
              </div>
            </div>
          )}

          {/* Quality score pill */}
          {score != null && (
            <div className={`absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-white text-[10px] font-semibold leading-none ${scoreColor} backdrop-blur-sm`}>
              {score}/100
            </div>
          )}
        </div>

        {/* Card body */}
        <div className="p-3 flex flex-col gap-2 flex-1">
          <p className="text-[var(--tx1)] text-xs font-medium line-clamp-2 leading-snug min-h-[2rem]">
            {job.concept}
          </p>
          <div className="flex items-center justify-between gap-1 mt-auto">
            <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
              {job.domain && (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize border shrink-0 ${badge}`}>
                  {job.domain}
                </span>
              )}
              {date && <span className="text-[var(--tx6)] text-[10px] truncate">{date}</span>}
            </div>
            <div className="flex items-center gap-0.5 shrink-0">
              {job.description && (
                <button onClick={e => { e.stopPropagation(); setLightbox(true); }}
                  className="w-6 h-6 flex items-center justify-center rounded-md text-[var(--tx6)] hover:text-teal-400 hover:bg-teal-500/10 transition-colors" title="Description">
                  <FileText size={11} />
                </button>
              )}
              {job.image_url && (
                <a href={job.image_url} download="diagram.png" onClick={e => e.stopPropagation()}
                  className="w-6 h-6 flex items-center justify-center rounded-md text-[var(--tx6)] hover:text-teal-400 hover:bg-teal-500/10 transition-colors" title="Download">
                  <Download size={11} />
                </a>
              )}
              {job.conversation_id && (
                <button onClick={e => e.stopPropagation()}
                  className="w-6 h-6 flex items-center justify-center rounded-md text-[var(--tx6)] hover:text-blue-400 hover:bg-blue-500/10 transition-colors" title="Go to chat">
                  <MessageSquare size={11} />
                </button>
              )}
              {job.status === 'failed' && (
                <button onClick={e => { e.stopPropagation(); handleRetry(); }} disabled={retrying}
                  className="w-6 h-6 flex items-center justify-center rounded-md text-teal-400 hover:bg-teal-500/15 transition-colors" title="Retry">
                  <RefreshCw size={11} className={retrying ? 'animate-spin' : ''} />
                </button>
              )}
              <button onClick={e => { e.stopPropagation(); handleDelete(); }} disabled={deleting}
                className="w-6 h-6 flex items-center justify-center rounded-md text-[var(--tx7)] hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
                <Trash2 size={11} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Lightbox */}
      {lightbox && job.image_url && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-6"
          onClick={() => setLightbox(false)}>
          <button onClick={() => setLightbox(false)}
            className="absolute top-5 right-5 w-9 h-9 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white">
            <X size={17} />
          </button>
          <div className="max-w-3xl w-full flex flex-col gap-4" onClick={e => e.stopPropagation()}>
            <img src={job.image_url} alt={job.concept}
              className="w-full rounded-xl shadow-2xl object-contain max-h-[65vh] bg-white" />
            {job.description && (
              <div className="bg-white/5 border border-white/10 rounded-xl px-5 py-4">
                <p className="text-white/50 text-[10px] uppercase tracking-wide font-medium mb-2">About this diagram</p>
                <p className="text-white/75 text-sm leading-relaxed whitespace-pre-wrap">{job.description}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

/* ── DiagramsGallery ───────────────────────────────────────────────────────── */
interface DiagramsGalleryProps {
  conversationId?: string;
  studySetId?: string;
  userId?: string;
  sessionId?: string;
  token?: string;
  /** Called when a new job is added externally so the gallery can refresh */
  refreshKey?: number;
}

export function DiagramsGallery({
  conversationId, studySetId, userId, sessionId, token, refreshKey,
}: DiagramsGalleryProps) {
  const [jobs,    setJobs]    = useState<EduImageJob[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await listEduImages({ conversation_id: conversationId, study_set_id: studySetId, user_id: userId, session_id: sessionId }, token);
      setJobs(data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [conversationId, studySetId, userId, sessionId, token]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const removeJob = useCallback((id: string) => {
    setJobs(prev => prev.filter(j => j.id !== id));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-[var(--tx7)]">
        <Loader size={18} className="animate-spin" />
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center px-6">
        <div className="w-12 h-12 rounded-2xl bg-teal-500/10 flex items-center justify-center mb-3">
          <ImageIcon size={22} className="text-teal-400" />
        </div>
        <p className="text-[var(--tx3)] text-sm font-medium">No diagrams yet</p>
        <p className="text-[var(--tx7)] text-xs mt-1">
          Click <span className="text-teal-400 font-medium">Sketch it</span> on any AI response
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 p-1">
      {jobs.map(job => (
        <ImageCard key={job.id ?? job.jobId} job={job} token={token} onRemove={removeJob} />
      ))}
    </div>
  );
}
