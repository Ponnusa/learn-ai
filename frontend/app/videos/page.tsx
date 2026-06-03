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
  ChevronLeft, ChevronRight, Video,
} from 'lucide-react';
import { getVideoStatus, retryVideoManim, getUserVideos, getSessionVideos } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import { Sidebar } from '@/components/layout/Sidebar';
import { preprocessMath } from '@/lib/preprocessMath';

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const STEPS = [
  'Writing solution & script',   // pending
  'Generating Manim animation',  // transcript_ready
  'Queued for rendering',        // queued
  'Rendering video',             // rendering
];
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

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7)  return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

// ─────────────────────────────────────────────────────────────────────────────
// TranscriptModal
// ─────────────────────────────────────────────────────────────────────────────

function TranscriptModal({
  markdown, onClose,
}: { markdown: string; onClose: () => void }) {
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
            <h2 className="text-[var(--tx1)] font-semibold text-sm">Solution &amp; Transcript</h2>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors"
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 chat-scroll px-6 py-5">
          <div className="ai-content text-sm leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
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
            Close
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
}: {
  v: VideoItem;
  onTranscript: (markdown: string) => void;
  onGoToConversation: (conversationId: string) => void;
}) {
  const router   = useRouter();
  const { gradient, badge } = subjectStyle(v.subject);
  const duration = formatDuration(v.duration_secs);
  const date     = formatDate(v.created_at);
  const title    = v.prompt || 'Untitled Video';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => router.push(`/videos?id=${v.id}`)}
      onKeyDown={e => { if (e.key === 'Enter') router.push(`/videos?id=${v.id}`); }}
      className="group bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden
                 cursor-pointer hover:border-purple-500/30
                 hover:shadow-xl hover:shadow-purple-500/8
                 transition-all duration-200 flex flex-col"
    >
      {/* ── Thumbnail ── */}
      <div className={`aspect-video relative overflow-hidden bg-gradient-to-br ${gradient} shrink-0`}>
        {v.thumbnail_url ? (
          <img src={v.thumbnail_url} alt={title} className="w-full h-full object-cover" />
        ) : v.video_url ? (
          <video
            src={v.video_url}
            muted
            playsInline
            preload="metadata"
            className="w-full h-full object-cover"
          />
        ) : (
          /* Decorative gradient overlay with play icon */
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-14 h-14 rounded-full bg-white/5 border border-white/10
                            flex items-center justify-center">
              <Play size={22} className="text-white/30 ml-1" />
            </div>
          </div>
        )}

        {/* Play overlay on hover */}
        <div className="absolute inset-0 flex items-center justify-center
                        opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
          <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full
                          flex items-center justify-center ring-1 ring-white/30">
            <Play size={20} className="text-white ml-0.5" fill="currentColor" />
          </div>
        </div>

        {/* Duration pill */}
        {duration && (
          <div className="absolute bottom-2 right-2 px-1.5 py-0.5
                          bg-black/70 backdrop-blur-sm rounded text-white text-[10px] font-mono
                          leading-none">
            {duration}
          </div>
        )}
      </div>

      {/* ── Card body ── */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        {/* Title */}
        <p className="text-[var(--tx1)] text-sm font-medium line-clamp-2 leading-snug
                      min-h-[2.5rem]">
          {title}
        </p>

        {/* Footer row: badge + date | action buttons */}
        <div className="flex items-center justify-between gap-1 mt-auto">
          <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
            {v.subject && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize
                               border shrink-0 ${badge}`}>
                {v.subject}
              </span>
            )}
            <span className="text-[var(--tx6)] text-xs truncate">{date}</span>
          </div>

          <div className="flex items-center gap-0.5 shrink-0">
            {v.transcript_markdown && (
              <button
                onClick={e => { e.stopPropagation(); onTranscript(v.transcript_markdown!); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-purple-400 hover:bg-purple-500/10
                           transition-colors"
                title="View transcript"
                aria-label="View transcript"
              >
                <FileText size={13} />
              </button>
            )}
            {v.conversation_id && (
              <button
                onClick={e => { e.stopPropagation(); onGoToConversation(v.conversation_id!); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-blue-400 hover:bg-blue-500/10
                           transition-colors"
                title="Go to conversation"
                aria-label="Go to conversation"
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
  const { gradient } = subjectStyle(v.subject);
  const title = v.prompt || 'Untitled Video';
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
        <p className="text-[var(--tx6)] text-[10px] mt-0.5">{formatDate(v.created_at)}</p>
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
}: {
  videos: VideoItem[];
  loading: boolean;
  onTranscript: (markdown: string) => void;
  onGoToConversation: (conversationId: string) => void;
}) {
  const router     = useRouter();
  const [page, setPage] = useState(1);
  const totalPages = Math.ceil(videos.length / PAGE_SIZE);
  const pageVideos = videos.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader size={24} className="text-[var(--tx5)] animate-spin" />
      </div>
    );
  }

  if (!videos.length) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center py-16">
        <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] border border-[var(--bd)]
                        flex items-center justify-center mb-1">
          <Video size={26} className="text-[var(--tx5)]" />
        </div>
        <div>
          <h2 className="text-[var(--tx1)] font-semibold text-base mb-1">No videos yet</h2>
          <p className="text-[var(--tx5)] text-sm max-w-xs leading-relaxed">
            Generate an animated explanation from any chat message to see it here.
          </p>
        </div>
        <button
          onClick={() => router.push('/')}
          className="mt-1 px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm
                     rounded-xl transition-colors font-medium"
        >
          Start chatting
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Grid */}
      <div className="flex-1 chat-scroll px-3 sm:px-6 py-4 sm:py-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {pageVideos.map(v => (
            <VideoLibraryCard
              key={v.id}
              v={v}
              onTranscript={onTranscript}
              onGoToConversation={onGoToConversation}
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
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                 bg-[var(--ov2)] hover:bg-[var(--ov4)]
                 text-[var(--tx4)] hover:text-[var(--tx1)]
                 border border-[var(--bd)] transition-all"
    >
      <FileText size={11} />
      Solution &amp; Transcript
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
  const { token, user, sessionId, setActiveConversationId } = useSessionStore();

  const rawId   = searchParams.get('id');
  const videoId = rawId ? Number(rawId) : null;

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
    return (
      <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
        <Sidebar onNewChat={() => router.push('/')} />

        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-[var(--bd)] shrink-0">
            <h1 className="text-[var(--tx1)] font-semibold">My Videos</h1>
            {!videosLoading && videos.length > 0 && (
              <span className="px-2 py-0.5 bg-[var(--ov3)] rounded-full
                               text-[var(--tx5)] text-xs">
                {videos.length}
              </span>
            )}
          </div>

          {/* Grid */}
          <VideoLibraryGrid
            videos={videos}
            loading={videosLoading}
            onTranscript={openTranscript}
            onGoToConversation={handleGoToConversation}
          />
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
                          title="Solution & Transcript"
                          className="flex items-center gap-2 px-3 sm:px-4 py-2
                                     bg-[var(--ov3)] hover:bg-[var(--ov4)]
                                     rounded-xl text-[var(--tx2)] text-sm transition-colors"
                        >
                          <FileText size={14} />
                          <span className="hidden sm:inline">Solution &amp; Transcript</span>
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
                  <p className="text-[var(--tx1)] font-semibold">Video ready — loading player…</p>
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
                      title={retrying ? 'Retrying…' : transcript ? 'Retry Video Generation' : 'Regenerate Video'}
                      className="flex items-center gap-2 px-4 sm:px-5 py-2.5
                                 bg-purple-600 hover:bg-purple-500
                                 disabled:opacity-50 text-white text-sm rounded-xl transition-colors"
                    >
                      <RefreshCw size={14} className={retrying ? 'animate-spin' : ''} />
                      <span className="hidden sm:inline">
                        {retrying ? 'Retrying…' : transcript ? 'Retry Video Generation' : 'Regenerate Video'}
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
            <p className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wide">My Videos</p>
          </div>
          {videosLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader size={16} className="text-[var(--tx5)] animate-spin" />
            </div>
          ) : videos.length === 0 ? (
            <div className="flex-1 flex items-center justify-center px-4">
              <p className="text-[var(--tx6)] text-xs text-center">No completed videos yet.</p>
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
