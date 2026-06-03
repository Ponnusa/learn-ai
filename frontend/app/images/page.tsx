'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Sparkles, Loader2, Download, RefreshCw,
  FlaskConical, Sigma, Leaf, Globe, BookOpen,
  ZoomIn, X, Clock, MessageSquare,
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useSessionStore } from '@/store/sessionStore';
import { generateEduImage, getEduImageJob, listEduImages, EduImageJob } from '@/lib/api';

// ── Domain metadata ───────────────────────────────────────────────────────────

const DOMAIN_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  physics:     { label: 'Physics',     icon: <Sparkles size={12} />,     color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  chemistry:   { label: 'Chemistry',   icon: <FlaskConical size={12} />, color: 'text-green-400 bg-green-500/10 border-green-500/20' },
  mathematics: { label: 'Mathematics', icon: <Sigma size={12} />,        color: 'text-violet-400 bg-violet-500/10 border-violet-500/20' },
  biology:     { label: 'Biology',     icon: <Leaf size={12} />,         color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  geography:   { label: 'Geography',   icon: <Globe size={12} />,        color: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
  general:     { label: 'Education',   icon: <BookOpen size={12} />,     color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20' },
};

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

// ── DomainBadge ───────────────────────────────────────────────────────────────

function DomainBadge({ domain }: { domain?: string }) {
  if (!domain) return null;
  const m = DOMAIN_META[domain] ?? DOMAIN_META.general;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ${m.color}`}>
      {m.icon} {m.label}
    </span>
  );
}

// ── ImageLightbox ─────────────────────────────────────────────────────────────

function ImageLightbox({ src, title, onClose }: { src: string; title: string; onClose: () => void }) {
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
      <img src={src} alt={title}
        style={{ transform: `scale(${zoom})`, transition: 'transform 0.15s ease', transformOrigin: 'center' }}
        className="max-w-[90vw] max-h-[90vh] object-contain rounded-xl select-none"
        onClick={e => { e.stopPropagation(); setZoom(z => z === 1 ? 2 : 1); }}
        draggable={false}
      />
      <p className="absolute bottom-4 text-white/25 text-xs select-none pointer-events-none">
        Click to toggle zoom · Esc to close
      </p>
    </div>
  );
}

// ── ImageCard ─────────────────────────────────────────────────────────────────

function ImageCard({ job, onClick, onGoToChat }: {
  job: EduImageJob;
  onClick: () => void;
  onGoToChat?: () => void;
}) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden
                    hover:border-indigo-500/30 transition-all group">
      {job.image_url ? (
        <button className="w-full aspect-square overflow-hidden bg-white relative"
          onClick={onClick}>
          <img src={job.image_url} alt={job.concept}
            className="w-full h-full object-contain group-hover:scale-[1.02] transition-transform duration-300" />
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/15 transition-colors
                          flex items-center justify-center opacity-0 group-hover:opacity-100">
            <div className="bg-black/60 rounded-full p-2.5">
              <ZoomIn size={18} className="text-white" />
            </div>
          </div>
        </button>
      ) : (
        <div className="w-full aspect-square bg-[var(--ov2)] flex items-center justify-center">
          {job.status === 'processing'
            ? <Loader2 size={24} className="text-indigo-400 animate-spin" />
            : <span className="text-[var(--tx6)] text-xs">Failed</span>}
        </div>
      )}
      <div className="p-3 space-y-2">
        <p className="text-[var(--tx2)] text-xs font-medium leading-snug line-clamp-2">
          {job.concept}
        </p>
        <div className="flex items-center justify-between gap-2">
          <DomainBadge domain={job.domain} />
          {job.status === 'processing' && (
            <span className="text-[10px] text-yellow-400 flex items-center gap-1">
              <Loader2 size={9} className="animate-spin" /> Generating…
            </span>
          )}
          {job.status === 'failed' && (
            <span className="text-[10px] text-red-400">Failed</span>
          )}
        </div>
        {/* Go to chat link — shown when diagram was created from a conversation */}
        {onGoToChat && job.status === 'ready' && (
          <button
            onClick={e => { e.stopPropagation(); onGoToChat(); }}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px]
                       font-medium text-indigo-400 hover:text-indigo-300
                       bg-indigo-500/8 hover:bg-indigo-500/15 border border-indigo-500/20
                       transition-colors"
          >
            <MessageSquare size={10} /> Go to chat message
          </button>
        )}
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
        <ImageLightbox src={lightbox.image_url!} title={lightbox.concept} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}
