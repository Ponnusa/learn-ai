'use client';
import { useState, useEffect, useCallback } from 'react';
import { ImageIcon, RefreshCw, Trash2, X, ZoomIn, AlertCircle, Loader, ChevronDown } from 'lucide-react';
import {
  listEduImages, deleteEduImage, retryEduImage, getEduImageJob,
  type EduImageJob,
} from '@/lib/api';

const DOMAIN_COLORS: Record<string, string> = {
  physics:     'bg-blue-500/15 text-blue-400 border-blue-500/25',
  chemistry:   'bg-green-500/15 text-green-400 border-green-500/25',
  mathematics: 'bg-purple-500/15 text-purple-400 border-purple-500/25',
  biology:     'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  geography:   'bg-amber-500/15 text-amber-400 border-amber-500/25',
  general:     'bg-[var(--ov3)] text-[var(--tx5)] border-[var(--bd)]',
};

function DomainBadge({ domain }: { domain?: string }) {
  const d = domain ?? 'general';
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${DOMAIN_COLORS[d] ?? DOMAIN_COLORS.general}`}>
      {d}
    </span>
  );
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
  const [job,         setJob]         = useState<EduImageJob>(initial);
  const [lightbox,    setLightbox]    = useState(false);
  const [showDesc,    setShowDesc]    = useState(false);
  const [retrying,    setRetrying]    = useState(false);
  const [deleting,    setDeleting]    = useState(false);

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

  return (
    <>
      <div className="rounded-xl border border-[var(--bd)] bg-[var(--surface)] overflow-hidden flex flex-col group">
        {/* Image area */}
        <div className="relative bg-white aspect-square flex items-center justify-center overflow-hidden">
          {job.status === 'ready' && job.image_url ? (
            <>
              <img
                src={job.image_url}
                alt={job.concept}
                className="w-full h-full object-contain cursor-zoom-in"
                onClick={() => setLightbox(true)}
              />
              <button
                onClick={() => setLightbox(true)}
                className="absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-lg
                           bg-black/40 text-white opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <ZoomIn size={13} />
              </button>
            </>
          ) : job.status === 'processing' ? (
            <div className="flex flex-col items-center gap-2 text-[var(--tx7)]">
              <Loader size={22} className="animate-spin text-teal-400" />
              <span className="text-[10px]">Generating…</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-[var(--tx7)]">
              <AlertCircle size={22} className="text-red-400" />
              <span className="text-[10px]">Failed</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-3 py-2.5 space-y-2">
          <p className="text-[var(--tx2)] text-xs font-medium line-clamp-2 leading-snug">{job.concept}</p>
          <div className="flex items-center justify-between gap-1.5">
            <DomainBadge domain={job.domain} />
            <div className="flex items-center gap-1">
              {job.description && (
                <button
                  onClick={() => setShowDesc(v => !v)}
                  className="w-6 h-6 flex items-center justify-center rounded-md
                             text-[var(--tx6)] hover:text-[var(--tx2)] hover:bg-[var(--ov3)] transition-colors"
                  title="More info"
                >
                  <ChevronDown size={11} className={`transition-transform ${showDesc ? 'rotate-180' : ''}`} />
                </button>
              )}
              {job.status === 'failed' && (
                <button
                  onClick={handleRetry}
                  disabled={retrying}
                  className="w-6 h-6 flex items-center justify-center rounded-md
                             text-teal-400 hover:bg-teal-500/15 transition-colors"
                  title="Retry"
                >
                  <RefreshCw size={11} className={retrying ? 'animate-spin' : ''} />
                </button>
              )}
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="w-6 h-6 flex items-center justify-center rounded-md
                           text-[var(--tx7)] hover:text-red-400 hover:bg-red-500/10 transition-colors"
                title="Delete"
              >
                <Trash2 size={11} />
              </button>
            </div>
          </div>

          {/* Description toggle */}
          {showDesc && job.description && (
            <p className="text-[var(--tx4)] text-[11px] leading-relaxed border-t border-[var(--bd)] pt-2 whitespace-pre-wrap">
              {job.description}
            </p>
          )}
        </div>
      </div>

      {/* Lightbox */}
      {lightbox && job.image_url && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-6"
          onClick={() => setLightbox(false)}
        >
          <button
            onClick={() => setLightbox(false)}
            className="absolute top-5 right-5 w-9 h-9 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white"
          >
            <X size={17} />
          </button>
          <div className="max-w-3xl w-full" onClick={e => e.stopPropagation()}>
            <img
              src={job.image_url}
              alt={job.concept}
              className="w-full rounded-xl shadow-2xl object-contain max-h-[80vh] bg-white"
            />
            <p className="mt-3 text-center text-white/70 text-sm">{job.concept}</p>
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
