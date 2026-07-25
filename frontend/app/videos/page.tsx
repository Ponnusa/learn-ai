'use client';
import { useEffect, useState, Suspense, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import {
  ArrowLeft, Download, CheckCircle, XCircle, Loader,
  RefreshCw, FileText, X, Play, MessageSquare,
  ChevronLeft, ChevronRight, Video, Sparkles,
} from 'lucide-react';
import { getVideoStatus, retryVideoManim, getUserVideos, getSessionVideos, generateVideo } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import { useLanguageStore } from '@/store/languageStore';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';
import { VideosTour } from '@/components/onboarding/VideosTour';
import { HelpCircle } from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

// STEPS is now built from translations inside VideosContent
const LOADING_STATUSES = new Set(['pending', 'queued', 'transcript_ready', 'rendering']);
const DONE_STATUSES    = new Set(['complete', 'completed']);
const PAGE_SIZE        = 12;

function statusToStepIdx(status: string): number {
  switch (status) {
    case 'pending':          return 0;
    case 'transcript_ready': return 1;
    case 'queued':           return 2;
    case 'rendering':        return 3;
    default:                 return 0;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type VideoItem = {
  id: number;
  status: string;
  video_url?: string;
  thumbnail_url?: string;
  prompt?: string;
  subject?: string;
  duration_secs?: number;
  created_at: string;
  transcript_markdown?: string;
  conversation_id?: string;
  message_id?: string;
  error_message?: string;
  concept_title?: string;
  course_name?: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

const SUBJECT_STYLES: Record<string, { badge: string; gradient: string }> = {
  mathematics: {
    badge:    'bg-purple-500/15 text-purple-400 border-purple-500/20',
    gradient: 'from-purple-950 via-indigo-950 to-slate-900',
  },
  physics: {
    badge:    'bg-blue-500/15 text-blue-400 border-blue-500/20',
    gradient: 'from-blue-950 via-cyan-950 to-slate-900',
  },
  chemistry: {
    badge:    'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    gradient: 'from-emerald-950 via-teal-950 to-slate-900',
  },
};
const DEFAULT_SUBJECT_STYLE = {
  badge:    'bg-[var(--ov3)] text-[var(--tx5)] border-[var(--bd)]',
  gradient: 'from-gray-900 via-slate-900 to-zinc-900',
};

function subjectStyle(s?: string) {
  return SUBJECT_STYLES[(s || '').toLowerCase()] ?? DEFAULT_SUBJECT_STYLE;
}

function formatDuration(secs?: number): string {
  if (!secs) return '';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function statusLabel(status: string): string {
  switch (status) {
    case 'pending':          return 'Writing script…';
    case 'transcript_ready': return 'Generating animation…';
    case 'queued':           return 'Queued for render…';
    case 'rendering':        return 'Rendering…';
    default:                 return 'Processing…';
  }
}

function formatDate(iso: string, todayStr: string, yesterdayStr: string, daysAgoTpl: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return todayStr;
  if (diffDays === 1) return yesterdayStr;
  if (diffDays < 7)  return daysAgoTpl.replace('{n}', String(diffDays));
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// ─────────────────────────────────────────────────────────────────────────────
// TranscriptModal
// ─────────────────────────────────────────────────────────────────────────────

function TranscriptModal({
  markdown, onClose,
}: { markdown: string; onClose: () => void }) {
  const { t } = useTranslation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl
                      w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl shadow-black/40">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)] shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-purple-600/20 flex items-center justify-center">
              <FileText size={13} className="text-purple-400" />
            </div>
            <h2 className="text-[var(--tx1)] font-semibold text-sm">{t.video.solutionTranscript}</h2>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors"
            aria-label={t.close}
          >
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 chat-scroll px-6 py-5">
          <div className="ai-content text-sm leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}>
              {preprocessMath(markdown)}
            </ReactMarkdown>
          </div>
        </div>

        <div className="px-5 py-3 border-t border-[var(--bd)] shrink-0 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs rounded-lg bg-[var(--ov3)] hover:bg-[var(--ov4)]
                       text-[var(--tx2)] transition-colors"
          >
            {t.close}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VideoLibraryCard  (full grid card)
// ─────────────────────────────────────────────────────────────────────────────

function VideoLibraryCard({
  v,
  onTranscript,
  onGoToConversation,
  onRetry,
}: {
  v: VideoItem;
  onTranscript: (markdown: string) => void;
  onGoToConversation: (conversationId: string) => void;
  onRetry?: (id: number) => void;
}) {
  const router   = useRouter();
  const { t }    = useTranslation();
  const { gradient, badge } = subjectStyle(v.subject);
  const duration  = formatDuration(v.duration_secs);
  const date      = formatDate(v.created_at, t.sidebar.today, t.sidebar.yesterday, t.studySets.daysAgo);
  const title     = v.concept_title || v.prompt || 'Untitled Video';
  const context   = v.course_name || null;
  const inProgress = LOADING_STATUSES.has(v.status);
  const isFailed   = v.status === 'failed';
  const isDone     = DONE_STATUSES.has(v.status);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => router.push(`/videos?id=${v.id}`)}
      onKeyDown={e => { if (e.key === 'Enter') router.push(`/videos?id=${v.id}`); }}
      className={`group bg-[var(--surface)] border rounded-2xl overflow-hidden cursor-pointer
                  transition-all duration-200 flex flex-col
                  ${isFailed
                    ? 'border-red-500/20 hover:border-red-500/40'
                    : 'border-[var(--bd)] hover:border-purple-500/30 hover:shadow-xl hover:shadow-purple-500/8'
                  }`}
    >
      {/* ── Thumbnail / status area ── */}
      <div className={`aspect-video relative overflow-hidden shrink-0 bg-gradient-to-br
                       ${isFailed ? 'from-red-950 via-slate-900 to-zinc-900' : gradient}`}>

        {/* In-progress overlay */}
        {inProgress && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <div className="w-10 h-10 rounded-full border-2 border-purple-500/30 border-t-purple-400 animate-spin" />
            <span className="text-white/50 text-[11px]">{statusLabel(v.status)}</span>
          </div>
        )}

        {/* Failed overlay */}
        {isFailed && (
          <div className="absolute inset-0 flex items-center justify-center">
            <XCircle size={32} className="text-red-400/40" />
          </div>
        )}

        {/* Done: thumbnail / video */}
        {isDone && (
          <>
            {v.thumbnail_url ? (
              <img src={v.thumbnail_url} alt={title} className="w-full h-full object-cover" />
            ) : v.video_url ? (
              <video src={v.video_url} muted playsInline preload="metadata"
                     className="w-full h-full object-cover" />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-14 h-14 rounded-full bg-white/5 border border-white/10
                                flex items-center justify-center">
                  <Play size={22} className="text-white/30 ml-1" />
                </div>
              </div>
            )}
            {/* Play hover overlay */}
            <div className="absolute inset-0 flex items-center justify-center
                            opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
              <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full
                              flex items-center justify-center ring-1 ring-white/30">
                <Play size={20} className="text-white ml-0.5" fill="currentColor" />
              </div>
            </div>
            {duration && (
              <div className="absolute bottom-2 right-2 px-1.5 py-0.5
                              bg-black/70 backdrop-blur-sm rounded text-white text-[10px] font-mono leading-none">
                {duration}
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Card body ── */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        <div className="min-h-[2.5rem]">
          <p className="text-[var(--tx1)] text-sm font-medium line-clamp-2 leading-snug">
            {title}
          </p>
          {context && (
            <p className="text-[var(--tx7)] text-[10px] mt-0.5 truncate">{context}</p>
          )}
        </div>

        <div className="flex items-center justify-between gap-1 mt-auto">
          <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
            {isFailed ? (
              <span className="text-red-400 text-[10px] font-medium">Failed</span>
            ) : inProgress ? (
              <span className="text-amber-400 text-[10px] font-medium">In progress</span>
            ) : (
              <>
                {v.subject && (
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize
                                   border shrink-0 ${badge}`}>
                    {v.subject}
                  </span>
                )}
              </>
            )}
            <span className="text-[var(--tx6)] text-xs truncate">{date}</span>
          </div>

          <div className="flex items-center gap-0.5 shrink-0">
            {isFailed && onRetry && (
              <button
                onClick={e => { e.stopPropagation(); onRetry(v.id); }}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium
                           bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                title="Retry video generation"
              >
                <RefreshCw size={10} /> Retry
              </button>
            )}
            {!isFailed && v.transcript_markdown && (
              <button
                onClick={e => { e.stopPropagation(); onTranscript(v.transcript_markdown!); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-purple-400 hover:bg-purple-500/10
                           transition-colors"
                title="View transcript"
              >
                <FileText size={13} />
              </button>
            )}
            {!isFailed && v.conversation_id && (
              <button
                onClick={e => { e.stopPropagation(); onGoToConversation(v.conversation_id!); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-blue-400 hover:bg-blue-500/10
                           transition-colors"
                title="Go to conversation"
              >
                <MessageSquare size={13} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VideoSidebarCard  (compact sidebar card in detail view)
// ─────────────────────────────────────────────────────────────────────────────

function VideoSidebarCard({
  v, active, onClick,
}: { v: VideoItem; active: boolean; onClick: () => void }) {
  const { t }        = useTranslation();
  const { gradient } = subjectStyle(v.subject);
  const title = v.concept_title || v.prompt || 'Untitled Video';
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex gap-2.5 px-2.5 py-2 rounded-xl transition-colors
        ${active
          ? 'bg-purple-500/15 border border-purple-500/30'
          : 'hover:bg-[var(--ov3)] border border-transparent'
        }`}
    >
      <div className={`w-16 h-10 rounded-lg overflow-hidden bg-gradient-to-br ${gradient}
                       flex-shrink-0 flex items-center justify-center`}>
        {v.video_url ? (
          <video src={v.video_url} muted playsInline preload="metadata"
                 className="w-full h-full object-cover" />
        ) : (
          <Play size={12} className="text-white/30" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[var(--tx2)] text-xs font-medium truncate leading-snug">
          {title}
        </p>
        <p className="text-[var(--tx6)] text-[10px] mt-0.5">{formatDate(v.created_at, t.sidebar.today, t.sidebar.yesterday, t.studySets.daysAgo)}</p>
      </div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VideoLibraryGrid  (grid + pagination for the library view)
// ─────────────────────────────────────────────────────────────────────────────

function VideoLibraryGrid({
  videos,
  loading,
  onTranscript,
  onGoToConversation,
  onRetry,
  embedded = false,
  emptyTitle,
  emptyDesc,
  emptyEmbeddedTitle,
  emptyEmbeddedDesc,
  pastVideosLabel,
}: {
  videos: VideoItem[];
  loading: boolean;
  onTranscript: (markdown: string) => void;
  onGoToConversation: (conversationId: string) => void;
  onRetry?: (id: number) => void;
  embedded?: boolean;
  emptyTitle?: string;
  emptyDesc?: string;
  emptyEmbeddedTitle?: string;
  emptyEmbeddedDesc?: string;
  pastVideosLabel?: string;
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.ceil(videos.length / PAGE_SIZE);
  const pageVideos = videos.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) {
    return (
      <div className={`flex items-center justify-center ${embedded ? 'py-10' : 'flex-1'}`}>
        <Loader size={24} className="text-[var(--tx5)] animate-spin" />
      </div>
    );
  }

  if (!videos.length) {
    if (embedded) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-[var(--ov2)] border border-[var(--bd)] flex items-center justify-center">
            <Video size={18} className="text-[var(--tx6)]" />
          </div>
          <p className="text-[var(--tx5)] text-sm">{emptyEmbeddedTitle ?? 'No videos generated yet.'}</p>
          <p className="text-[var(--tx7)] text-xs">{emptyEmbeddedDesc ?? 'Type a topic above and click Generate.'}</p>
        </div>
      );
    }
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center py-16">
        <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] border border-[var(--bd)]
                        flex items-center justify-center mb-1">
          <Video size={26} className="text-[var(--tx5)]" />
        </div>
        <div>
          <h2 className="text-[var(--tx1)] font-semibold text-base mb-1">{emptyTitle ?? 'No videos yet'}</h2>
          <p className="text-[var(--tx5)] text-sm max-w-xs leading-relaxed">
            {emptyDesc ?? 'Generate an animated explanation from any topic above.'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Section header when embedded */}
      {embedded && videos.length > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <Video size={13} className="text-[var(--tx6)]" />
          <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">
            {pastVideosLabel ?? 'Past videos'} · {videos.length}
          </p>
        </div>
      )}

      {/* Grid */}
      <div className={embedded ? '' : 'flex-1 chat-scroll px-3 sm:px-6 py-4 sm:py-6'}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {pageVideos.map(v => (
            <VideoLibraryCard
              key={v.id}
              v={v}
              onTranscript={onTranscript}
              onGoToConversation={onGoToConversation}
              onRetry={onRetry}
            />
          ))}
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1.5 py-4 border-t border-[var(--bd)] shrink-0">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="w-8 h-8 flex items-center justify-center rounded-lg
                       text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                       disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={16} />
          </button>

          {/* Page numbers — show at most 7 */}
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
            .reduce<(number | '…')[]>((acc, p, i, arr) => {
              if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push('…');
              acc.push(p);
              return acc;
            }, [])
            .map((p, i) =>
              p === '…' ? (
                <span key={`ellipsis-${i}`} className="w-8 text-center text-[var(--tx6)] text-sm">
                  …
                </span>
              ) : (
                <button
                  key={p}
                  onClick={() => setPage(p as number)}
                  className={`w-8 h-8 flex items-center justify-center rounded-lg text-sm
                              font-medium transition-colors
                    ${p === page
                      ? 'bg-purple-600 text-white'
                      : 'text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]'
                    }`}
                >
                  {p}
                </button>
              )
            )
          }

          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="w-8 h-8 flex items-center justify-center rounded-lg
                       text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                       disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Small transcript button (used in detail view)
// ─────────────────────────────────────────────────────────────────────────────

function TranscriptButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                 bg-[var(--ov2)] hover:bg-[var(--ov4)]
                 text-[var(--tx4)] hover:text-[var(--tx1)]
                 border border-[var(--bd)] transition-all"
    >
      <FileText size={11} />
      {t.video.solutionTranscript}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main content
// ─────────────────────────────────────────────────────────────────────────────

function VideosContent() {
  const searchParams                  = useSearchParams();
  const router                        = useRouter();
  const { t }                         = useTranslation();
  const { language }                  = useLanguageStore();
  const { token, user, sessionId, setActiveConversationId } = useSessionStore();

  const rawId   = searchParams.get('id');
  const videoId = rawId ? Number(rawId) : null;

  const STEPS = [
    t.video.writingScript,
    t.video.generatingAnimation,
    t.video.queuedRendering,
    t.video.renderingVideo,
  ];

  // Current video (detail view)
  const [status,     setStatus]     = useState('pending');
  const [videoUrl,   setVideoUrl]   = useState<string | null>(null);
  const [error,      setError]      = useState<string | null>(null);
  const [stepIdx,    setStepIdx]    = useState(0);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [retrying,   setRetrying]   = useState(false);
  const [showModal,  setShowModal]  = useState(false);
  const [modalText,  setModalText]  = useState<string>('');
  const [retryTick,  setRetryTick]  = useState(0);

  // Videos list (both views)
  const [videos,        setVideos]        = useState<VideoItem[]>([]);
  const [videosLoading, setVideosLoading] = useState(true);

  // Generation prompt (library view)
  const [genTopic,      setGenTopic]      = useState('');
  const [generating,    setGenerating]    = useState(false);
  const [genError,      setGenError]      = useState<string | null>(null);

  const closeModal = useCallback(() => setShowModal(false), []);

  function openTranscript(md: string) {
    setModalText(md);
    setShowModal(true);
  }

  function handleGoToConversation(conversationId: string) {
    setActiveConversationId(conversationId);
    router.push('/');
  }

  // Poll current video (detail view)
  useEffect(() => {
    if (!videoId) return;
    let stopped = false;

    async function poll() {
      try {
        const data = await getVideoStatus(videoId!, token ?? undefined);
        if (stopped) return;
        setStatus(data.status);
        if (data.transcript_markdown) setTranscript(data.transcript_markdown);

        if (DONE_STATUSES.has(data.status)) { setVideoUrl(data.video_url ?? null); return; }
        if (data.status === 'failed')       { setError(data.error_message ?? t.errors.videoFailed); return; }

        setStepIdx(statusToStepIdx(data.status));
        setTimeout(poll, 4000);
      } catch {
        if (!stopped) setError(t.errors.generic);
      }
    }
    poll();
    return () => { stopped = true; };
  }, [videoId, retryTick]);

  // Load videos list
  useEffect(() => {
    setVideosLoading(true);
    const load = user?.id
      ? getUserVideos(user.id, token ?? undefined)
      : sessionId
        ? getSessionVideos(sessionId)
        : Promise.resolve([]);
    load
      .then(r => { setVideos(r as VideoItem[]); setVideosLoading(false); })
      .catch(() => setVideosLoading(false));
  }, [user?.id, sessionId]);

  function refreshList() {
    const load = user?.id
      ? getUserVideos(user.id, token ?? undefined)
      : sessionId ? getSessionVideos(sessionId) : Promise.resolve([]);
    load.then(r => setVideos(r as VideoItem[])).catch(() => {});
  }

  async function handleRetryFromLibrary(videoId: number) {
    setVideos(prev => prev.map(v => v.id === videoId ? { ...v, status: 'pending' } : v));
    try {
      await retryVideoManim(videoId, token ?? undefined);
      router.push(`/videos?id=${videoId}`);
    } catch {
      refreshList();
    }
  }

  async function handleGenerate() {
    const topic = genTopic.trim();
    if (!topic || generating) return;
    setGenerating(true);
    setGenError(null);
    try {
      const res = await generateVideo({
        prompt:     topic,
        user_id:    user?.id,
        session_id: sessionId ?? undefined,
        language,
      }, token ?? undefined);
      if (!res.supported) {
        setGenError(res.message ?? 'Video generation not supported for this topic.');
        return;
      }
      setGenTopic('');
      router.push(`/videos?id=${res.video_id}`);
    } catch (e: any) {
      const isLimit = e?.message === 'session_limit_reached' || e?.message === 'Daily video limit reached';
      setGenError(isLimit
        ? '⚠️ Daily video limit reached. Come back tomorrow or upgrade your plan.'
        : (e?.message ?? 'Generation failed. Please try again.')
      );
    } finally {
      setGenerating(false);
    }
  }

  async function handleRetry() {
    if (!videoId) return;
    setRetrying(true);
    setError(null);
    setStatus('pending');
    setStepIdx(0);
    setVideoUrl(null);
    try {
      await retryVideoManim(videoId, token ?? undefined);
      refreshList();
      setRetryTick(n => n + 1);
    } catch (e: any) {
      setError(e.message ?? 'Retry failed');
    } finally {
      setRetrying(false);
    }
  }

  const isLoading = LOADING_STATUSES.has(status);
  const isDone    = DONE_STATUSES.has(status);
  const isFailed  = status === 'failed';

  // ── Library view (no ?id=) ────────────────────────────────────────────────
  if (!videoId) {
    const EXAMPLES = t.video.examples;

    return (
      <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
        <Sidebar onNewChat={() => router.push('/')} />

        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <VideosTour />
          <MobileTopBar />
          {/* Header */}
          <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-[var(--bd)] shrink-0">
            <div className="flex-1 min-w-0">
              <h1 className="text-[var(--tx1)] font-semibold">{t.video.studio}</h1>
              <p className="text-[var(--tx6)] text-xs mt-0.5">{t.video.studioDesc}</p>
            </div>
            <button
              onClick={() => window.dispatchEvent(new CustomEvent('start-videos-tour'))}
              className="flex items-center gap-1 text-[11px] text-[var(--tx7)] hover:text-purple-400 transition-colors px-2 py-1"
              title="Take a tour"
            >
              <HelpCircle size={13} />
            </button>
            {!videosLoading && videos.length > 0 && (
              <span className="px-2 py-0.5 bg-[var(--ov3)] rounded-full text-[var(--tx5)] text-xs shrink-0">
                {videos.length}
              </span>
            )}
          </div>

          <div className="flex-1 chat-scroll">
            <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-8">
              {/* ── Generation prompt ─────────────────────────────── */}
              <div className="space-y-3">
                <div className="relative">
                  <textarea
                    data-tour="video-input"
                    value={genTopic}
                    onChange={e => setGenTopic(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleGenerate(); } }}
                    placeholder={t.video.generatePlaceholder}
                    rows={2}
                    disabled={generating}
                    className="w-full px-4 py-3.5 pr-28 rounded-2xl bg-[var(--surface)] border border-[var(--bd)]
                               text-[var(--tx1)] text-sm placeholder-[var(--tx7)] resize-none
                               focus:outline-none focus:border-purple-500/50 disabled:opacity-60 transition-colors
                               leading-relaxed"
                  />
                  <button
                    onClick={handleGenerate}
                    disabled={!genTopic.trim() || generating}
                    className="absolute right-3 bottom-3 flex items-center gap-1.5 px-3 py-1.5 rounded-xl
                               text-xs font-semibold bg-purple-600 hover:bg-purple-500
                               disabled:opacity-40 text-white transition-colors"
                  >
                    {generating
                      ? <Loader size={12} className="animate-spin" />
                      : <Sparkles size={12} />}
                    {generating ? t.video.generatingBtn : t.video.generateBtn}
                  </button>
                </div>

                {/* Example pills */}
                <div data-tour="video-examples" className="flex flex-wrap gap-1.5">
                  {EXAMPLES.map(ex => (
                    <button key={ex} onClick={() => setGenTopic(ex)}
                      className="text-[10px] px-2.5 py-1 rounded-full bg-[var(--ov3)] hover:bg-[var(--ov4)]
                                 text-[var(--tx5)] hover:text-[var(--tx2)] border border-[var(--bd)]
                                 transition-colors truncate max-w-[200px]">
                      {ex}
                    </button>
                  ))}
                </div>

                {/* Error */}
                {genError && (
                  <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
                    {genError}
                  </p>
                )}
              </div>

              {/* ── Past videos ───────────────────────────────────── */}
              <VideoLibraryGrid
                videos={videos}
                loading={videosLoading}
                onTranscript={openTranscript}
                onGoToConversation={handleGoToConversation}
                onRetry={handleRetryFromLibrary}
                embedded
                emptyEmbeddedTitle={t.video.noCompletedYet}
                emptyEmbeddedDesc={t.video.generatePlaceholder}
                pastVideosLabel={t.video.pastVideos}
              />
            </div>
          </div>
        </main>

        {showModal && modalText && (
          <TranscriptModal markdown={modalText} onClose={closeModal} />
        )}
      </div>
    );
  }

  // ── Detail view (?id=…) ───────────────────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex min-w-0 overflow-hidden">

        {/* Left: video player / status */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <MobileTopBar />
          <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--bd)] shrink-0">
            <button
              onClick={() => router.back()}
              className="text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors"
              aria-label="Back"
            >
              <ArrowLeft size={20} />
            </button>
            <h1 className="text-[var(--tx1)] font-semibold flex-1">
              {isDone ? t.video.ready : isFailed ? t.video.failed : t.video.generating}
            </h1>
          </div>

          <div className="flex-1 chat-scroll">
            <div className="flex items-start justify-center px-3 sm:px-6 py-6 sm:py-10 min-h-full">

              {/* Loading */}
              {isLoading && (
                <div className="text-center max-w-sm w-full">
                  <div className="w-20 h-20 mx-auto mb-8 relative">
                    <div className="w-20 h-20 rounded-full border-4 border-[var(--bd)]" />
                    <div className="w-20 h-20 rounded-full border-4 border-purple-500 border-t-transparent
                                    absolute inset-0 animate-spin" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <img src="/logo-36.png" alt="Learn-AI" className="w-9 h-9 object-contain" />
                    </div>
                  </div>
                  <h2 className="text-[var(--tx1)] text-xl font-semibold mb-2">{t.video.generating}</h2>
                  <p className="text-[var(--tx5)] text-sm mb-8">{t.video.generatingDesc}</p>
                  <div className="space-y-3 text-left">
                    {STEPS.map((step, i) => {
                      const done = i < stepIdx, active = i === stepIdx;
                      return (
                        <div key={i} className="flex items-center gap-3">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                            done ? 'bg-green-500' : active ? 'bg-purple-500 animate-pulse' : 'bg-[var(--ov3)]'
                          }`}>
                            {done   && <CheckCircle size={12} className="text-white" />}
                            {active && <Loader size={10} className="text-white animate-spin" />}
                          </div>
                          <span className={`text-sm ${
                            done ? 'text-[var(--tx6)] line-through' : active ? 'text-[var(--tx1)]' : 'text-[var(--tx9)]'
                          }`}>
                            {step}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  {transcript && (
                    <div className="mt-8">
                      <TranscriptButton onClick={() => openTranscript(transcript)} />
                    </div>
                  )}
                </div>
              )}

              {/* Done — video player */}
              {isDone && videoUrl && (
                <div className="w-full max-w-3xl">
                  <div className="aspect-video rounded-2xl overflow-hidden bg-black
                                  shadow-2xl shadow-purple-500/10 mb-3">
                    <video src={videoUrl} controls autoPlay className="w-full h-full" />
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[var(--tx5)] text-sm min-w-0 truncate">✅ {t.video.ready}</p>
                    <div className="flex items-center gap-2 shrink-0">
                      {transcript && (
                        <button
                          onClick={() => openTranscript(transcript)}
                          title={t.video.solutionTranscript}
                          className="flex items-center gap-2 px-3 sm:px-4 py-2
                                     bg-[var(--ov3)] hover:bg-[var(--ov4)]
                                     rounded-xl text-[var(--tx2)] text-sm transition-colors"
                        >
                          <FileText size={14} />
                          <span className="hidden sm:inline">{t.video.solutionTranscript}</span>
                        </button>
                      )}
                      <a
                        href={videoUrl}
                        download
                        title="Download"
                        className="flex items-center gap-2 px-3 sm:px-4 py-2
                                   bg-[var(--ov3)] hover:bg-[var(--ov4)]
                                   rounded-xl text-[var(--tx2)] text-sm transition-colors"
                      >
                        <Download size={14} />
                        <span className="hidden sm:inline">{t.download}</span>
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {isDone && !videoUrl && (
                <div className="text-center flex flex-col items-center gap-4">
                  <CheckCircle size={48} className="text-green-400" />
                  <p className="text-[var(--tx1)] font-semibold">{t.video.loadingPlayer}</p>
                  {transcript && <TranscriptButton onClick={() => openTranscript(transcript)} />}
                </div>
              )}

              {/* Failed */}
              {isFailed && (
                <div className="text-center max-w-md flex flex-col items-center gap-5">
                  <XCircle size={48} className="text-red-400" />
                  <h2 className="text-[var(--tx1)] font-semibold">{t.video.failed}</h2>

                  {error && <p className="text-[var(--tx5)] text-sm">{error}</p>}

                  <div className="flex gap-3 flex-wrap justify-center">
                    <button
                      onClick={handleRetry}
                      disabled={retrying}
                      title={retrying ? t.video.retrying : transcript ? t.video.retryBtn : t.video.regenerateBtn}
                      className="flex items-center gap-2 px-4 sm:px-5 py-2.5
                                 bg-purple-600 hover:bg-purple-500
                                 disabled:opacity-50 text-white text-sm rounded-xl transition-colors"
                    >
                      <RefreshCw size={14} className={retrying ? 'animate-spin' : ''} />
                      <span className="hidden sm:inline">
                        {retrying ? t.video.retrying : transcript ? t.video.retryBtn : t.video.regenerateBtn}
                      </span>
                    </button>

                    <button
                      onClick={() => router.back()}
                      title={t.back}
                      className="flex items-center gap-2 px-4 sm:px-5 py-2.5
                                 bg-[var(--ov3)] hover:bg-[var(--ov4)]
                                 text-[var(--tx2)] text-sm rounded-xl transition-colors"
                    >
                      <ArrowLeft size={14} />
                      <span className="hidden sm:inline">{t.back}</span>
                    </button>
                  </div>

                  {transcript
                    ? <TranscriptButton onClick={() => openTranscript(transcript)} />
                    : <p className="text-[var(--tx6)] text-xs">Solution will be regenerated automatically on retry.</p>
                  }
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right sidebar: completed videos list — desktop only */}
        <aside className="hidden md:flex flex-col w-60 border-l border-[var(--bd)] overflow-hidden shrink-0">
          <div className="px-3 py-3 border-b border-[var(--bd)] shrink-0">
            <p className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wide">{t.video.studio}</p>
          </div>
          {videosLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader size={16} className="text-[var(--tx5)] animate-spin" />
            </div>
          ) : videos.length === 0 ? (
            <div className="flex-1 flex items-center justify-center px-4">
              <p className="text-[var(--tx6)] text-xs text-center">{t.video.noCompletedYet}</p>
            </div>
          ) : (
            <div className="flex-1 chat-scroll py-2 px-2 space-y-0.5">
              {videos.map(v => (
                <VideoSidebarCard
                  key={v.id}
                  v={v}
                  active={v.id === videoId}
                  onClick={() => router.push(`/videos?id=${v.id}`)}
                />
              ))}
            </div>
          )}
        </aside>
      </main>

      {showModal && modalText && (
        <TranscriptModal markdown={modalText} onClose={closeModal} />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export default function VideosPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <VideosContent />
    </Suspense>
  );
}
