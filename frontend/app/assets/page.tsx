'use client';
import { useEffect, useState, Suspense, useCallback, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import {
  ArrowLeft, Download, CheckCircle, XCircle, Loader,
  RefreshCw, FileText, X, Play, MessageSquare,
  ChevronLeft, ChevronRight, Video, Sparkles, ThumbsDown,
  ZoomIn, Clock, Trash2, AlertCircle, Loader2,
} from 'lucide-react';
import { getVideoStatus, retryVideo, getUserVideos, getSessionVideos, generateVideo, improveVideo } from '@/lib/api';
import { generateEduImage, getEduImageJob, listEduImages, deleteEduImage, retryEduImage, EduImageJob } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import { useLanguageStore } from '@/store/languageStore';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { SignupModal } from '@/components/gates/SignupModal';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';
import { VideosTour } from '@/components/onboarding/VideosTour';
import { ImagesTour } from '@/components/onboarding/ImagesTour';
import { HelpCircle } from 'lucide-react';
import { QualityBadge, QualityBanner } from '@/components/video/QualityBadge';

// ─────────────────────────────────────────────────────────────────────────────
// Video constants & types
// ─────────────────────────────────────────────────────────────────────────────

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
// Video helpers
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
  const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return todayStr;
  if (diffDays === 1) return yesterdayStr;
  if (diffDays < 7)  return daysAgoTpl.replace('{n}', String(diffDays));
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// ─────────────────────────────────────────────────────────────────────────────
// Image helpers
// ─────────────────────────────────────────────────────────────────────────────

const DOMAIN_STYLES: Record<string, { badge: string; gradient: string }> = {
  physics:     { badge: 'bg-blue-500/15 text-blue-400 border-blue-500/20',       gradient: 'from-blue-950 via-cyan-950 to-slate-900' },
  chemistry:   { badge: 'bg-green-500/15 text-green-400 border-green-500/20',    gradient: 'from-emerald-950 via-teal-950 to-slate-900' },
  mathematics: { badge: 'bg-purple-500/15 text-purple-400 border-purple-500/20', gradient: 'from-purple-950 via-indigo-950 to-slate-900' },
  biology:     { badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', gradient: 'from-emerald-950 via-green-950 to-slate-900' },
  geography:   { badge: 'bg-amber-500/15 text-amber-400 border-amber-500/20',    gradient: 'from-amber-950 via-yellow-950 to-slate-900' },
  general:     { badge: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/20', gradient: 'from-indigo-950 via-slate-900 to-zinc-900' },
};
const DEFAULT_DOMAIN_STYLE = { badge: 'bg-[var(--ov3)] text-[var(--tx5)] border-[var(--bd)]', gradient: 'from-gray-900 via-slate-900 to-zinc-900' };
function domainStyle(d?: string) { return DOMAIN_STYLES[(d || '').toLowerCase()] ?? DEFAULT_DOMAIN_STYLE; }

// ─────────────────────────────────────────────────────────────────────────────
// TranscriptModal
// ─────────────────────────────────────────────────────────────────────────────

function TranscriptModal({ markdown, onClose }: { markdown: string; onClose: () => void }) {
  const { t } = useTranslation();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl
                      w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl shadow-black/40">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)] shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-purple-600/20 flex items-center justify-center">
              <FileText size={13} className="text-purple-400" />
            </div>
            <h2 className="text-[var(--tx1)] font-semibold text-sm">{t.video.solutionTranscript}</h2>
          </div>
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors"
            aria-label={t.close}>
            <X size={15} />
          </button>
        </div>
        <div className="flex-1 min-h-0 chat-scroll px-6 py-5">
          <div className="ai-content text-sm leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}>
              {preprocessMath(markdown)}
            </ReactMarkdown>
          </div>
        </div>
        <div className="px-5 py-3 border-t border-[var(--bd)] shrink-0 flex justify-end">
          <button onClick={onClose}
            className="px-4 py-1.5 text-xs rounded-lg bg-[var(--ov3)] hover:bg-[var(--ov4)]
                       text-[var(--tx2)] transition-colors">
            {t.close}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FeedbackModal
// ─────────────────────────────────────────────────────────────────────────────

function FeedbackModal({ onClose, onSubmit, loading }: {
  onClose: () => void;
  onSubmit: (feedback: string) => Promise<void>;
  loading: boolean;
}) {
  const [text, setText] = useState('');
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !loading) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, loading]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget && !loading) onClose(); }}>
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl
                      w-full max-w-md flex flex-col shadow-2xl shadow-black/40">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)] shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-orange-500/15 flex items-center justify-center">
              <ThumbsDown size={13} className="text-orange-400" />
            </div>
            <h2 className="text-[var(--tx1)] font-semibold text-sm">Improve this video</h2>
          </div>
          <button onClick={onClose} disabled={loading}
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                       transition-colors disabled:opacity-40"
            aria-label="Close">
            <X size={15} />
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <p className="text-[var(--tx5)] text-xs leading-relaxed">
            Describe what needs fixing — layout issues, overlapping text, wrong panel placement, etc.
            The content and voiceover will be preserved exactly.
          </p>
          <textarea autoFocus value={text} onChange={e => setText(e.target.value)}
            disabled={loading} rows={4}
            placeholder="e.g. The molecule diagram overlaps the text. Move it further left."
            className="w-full px-3 py-2.5 rounded-xl bg-[var(--bg)] border border-[var(--bd)]
                       text-[var(--tx1)] text-sm placeholder-[var(--tx7)] resize-none
                       focus:outline-none focus:border-orange-500/50
                       disabled:opacity-60 transition-colors" />
        </div>
        <div className="px-5 py-3 border-t border-[var(--bd)] shrink-0 flex justify-end gap-2">
          <button onClick={onClose} disabled={loading}
            className="px-4 py-1.5 text-xs rounded-lg bg-[var(--ov3)] hover:bg-[var(--ov4)]
                       text-[var(--tx2)] transition-colors disabled:opacity-40">
            Cancel
          </button>
          <button onClick={() => onSubmit(text)} disabled={!text.trim() || loading}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg
                       bg-orange-600 hover:bg-orange-500 text-white
                       disabled:opacity-40 transition-colors">
            {loading
              ? <><Loader size={11} className="animate-spin" /> Regenerating…</>
              : <><RefreshCw size={11} /> Regenerate</>}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VideoLibraryCard
// ─────────────────────────────────────────────────────────────────────────────

function VideoLibraryCard({ v, onTranscript, onGoToConversation, onRetry }: {
  v: VideoItem;
  onTranscript: (markdown: string) => void;
  onGoToConversation: (conversationId: string) => void;
  onRetry?: (id: number) => void;
}) {
  const router = useRouter();
  const { t }  = useTranslation();
  const { gradient, badge } = subjectStyle(v.subject);
  const duration   = formatDuration(v.duration_secs);
  const date       = formatDate(v.created_at, t.sidebar.today, t.sidebar.yesterday, t.studySets.daysAgo);
  const title      = v.concept_title || v.prompt || 'Untitled Video';
  const context    = v.course_name || null;
  const inProgress = LOADING_STATUSES.has(v.status);
  const isFailed   = v.status === 'failed';
  const isDone     = DONE_STATUSES.has(v.status);

  return (
    <div role="button" tabIndex={0}
      onClick={() => router.push(`/assets?id=${v.id}`)}
      onKeyDown={e => { if (e.key === 'Enter') router.push(`/assets?id=${v.id}`); }}
      className={`group bg-[var(--surface)] border rounded-2xl overflow-hidden cursor-pointer
                  transition-all duration-200 flex flex-col
                  ${isFailed
                    ? 'border-red-500/20 hover:border-red-500/40'
                    : 'border-[var(--bd)] hover:border-purple-500/30 hover:shadow-xl hover:shadow-purple-500/8'}`}>
      <div className={`aspect-video relative overflow-hidden shrink-0 bg-gradient-to-br
                       ${isFailed ? 'from-red-950 via-slate-900 to-zinc-900' : gradient}`}>
        {inProgress && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <div className="w-10 h-10 rounded-full border-2 border-purple-500/30 border-t-purple-400 animate-spin" />
            <span className="text-white/50 text-[11px]">{statusLabel(v.status)}</span>
          </div>
        )}
        {isFailed && (
          <div className="absolute inset-0 flex items-center justify-center">
            <XCircle size={32} className="text-red-400/40" />
          </div>
        )}
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
      <div className="p-3 flex flex-col gap-2 flex-1">
        <div className="min-h-[2.5rem]">
          <p className="text-[var(--tx1)] text-sm font-medium line-clamp-2 leading-snug">{title}</p>
          {context && <p className="text-[var(--tx7)] text-[10px] mt-0.5 truncate">{context}</p>}
        </div>
        <div className="flex items-center justify-between gap-1 mt-auto">
          <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
            {isFailed ? (
              <span className="text-red-400 text-[10px] font-medium">Failed</span>
            ) : inProgress ? (
              <span className="text-amber-400 text-[10px] font-medium">In progress</span>
            ) : (
              v.subject && (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize
                                 border shrink-0 ${badge}`}>
                  {v.subject}
                </span>
              )
            )}
            <span className="text-[var(--tx6)] text-xs truncate">{date}</span>
          </div>
          <div className="flex items-center gap-0.5 shrink-0">
            {isFailed && onRetry && (
              <button onClick={e => { e.stopPropagation(); onRetry(v.id); }}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium
                           bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                title="Retry video generation">
                <RefreshCw size={10} /> Retry
              </button>
            )}
            {!isFailed && v.transcript_markdown && (
              <button onClick={e => { e.stopPropagation(); onTranscript(v.transcript_markdown!); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-purple-400 hover:bg-purple-500/10
                           transition-colors"
                title="View transcript">
                <FileText size={13} />
              </button>
            )}
            {!isFailed && v.conversation_id && (
              <button onClick={e => { e.stopPropagation(); onGoToConversation(v.conversation_id!); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-blue-400 hover:bg-blue-500/10
                           transition-colors"
                title="Go to conversation">
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
// VideoSidebarCard
// ─────────────────────────────────────────────────────────────────────────────

function VideoSidebarCard({ v, active, onClick }: { v: VideoItem; active: boolean; onClick: () => void }) {
  const { t }        = useTranslation();
  const { gradient } = subjectStyle(v.subject);
  const title = v.concept_title || v.prompt || 'Untitled Video';
  return (
    <button onClick={onClick}
      className={`w-full text-left flex gap-2.5 px-2.5 py-2 rounded-xl transition-colors
        ${active
          ? 'bg-purple-500/15 border border-purple-500/30'
          : 'hover:bg-[var(--ov3)] border border-transparent'}`}>
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
        <p className="text-[var(--tx2)] text-xs font-medium truncate leading-snug">{title}</p>
        <p className="text-[var(--tx6)] text-[10px] mt-0.5">
          {formatDate(v.created_at, t.sidebar.today, t.sidebar.yesterday, t.studySets.daysAgo)}
        </p>
      </div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VideoLibraryGrid
// ─────────────────────────────────────────────────────────────────────────────

function VideoLibraryGrid({
  videos, loading, onTranscript, onGoToConversation, onRetry,
  embedded = false, emptyTitle, emptyDesc, emptyEmbeddedTitle, emptyEmbeddedDesc, pastVideosLabel,
}: {
  videos: VideoItem[]; loading: boolean;
  onTranscript: (markdown: string) => void;
  onGoToConversation: (conversationId: string) => void;
  onRetry?: (id: number) => void;
  embedded?: boolean; emptyTitle?: string; emptyDesc?: string;
  emptyEmbeddedTitle?: string; emptyEmbeddedDesc?: string; pastVideosLabel?: string;
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
      {embedded && videos.length > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <Video size={13} className="text-[var(--tx6)]" />
          <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">
            {pastVideosLabel ?? 'Past videos'} · {videos.length}
          </p>
        </div>
      )}
      <div className={embedded ? '' : 'flex-1 chat-scroll px-3 sm:px-6 py-4 sm:py-6'}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {pageVideos.map(v => (
            <VideoLibraryCard key={v.id} v={v}
              onTranscript={onTranscript}
              onGoToConversation={onGoToConversation}
              onRetry={onRetry} />
          ))}
        </div>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1.5 py-4 border-t border-[var(--bd)] shrink-0">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="w-8 h-8 flex items-center justify-center rounded-lg
                       text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                       disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
            <ChevronLeft size={16} />
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
            .reduce<(number | '…')[]>((acc, p, i, arr) => {
              if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push('…');
              acc.push(p);
              return acc;
            }, [])
            .map((p, i) =>
              p === '…' ? (
                <span key={`ellipsis-${i}`} className="w-8 text-center text-[var(--tx6)] text-sm">…</span>
              ) : (
                <button key={p} onClick={() => setPage(p as number)}
                  className={`w-8 h-8 flex items-center justify-center rounded-lg text-sm font-medium transition-colors
                    ${p === page ? 'bg-purple-600 text-white' : 'text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]'}`}>
                  {p}
                </button>
              )
            )
          }
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="w-8 h-8 flex items-center justify-center rounded-lg
                       text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                       disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TranscriptButton
// ─────────────────────────────────────────────────────────────────────────────

function TranscriptButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();
  return (
    <button onClick={onClick}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                 bg-[var(--ov2)] hover:bg-[var(--ov4)]
                 text-[var(--tx4)] hover:text-[var(--tx1)]
                 border border-[var(--bd)] transition-all">
      <FileText size={11} />
      {t.video.solutionTranscript}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DomainBadge
// ─────────────────────────────────────────────────────────────────────────────

function DomainBadge({ domain }: { domain?: string }) {
  if (!domain) return null;
  const { badge } = domainStyle(domain);
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize border shrink-0 ${badge}`}>
      {domain}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ImageLightbox
// ─────────────────────────────────────────────────────────────────────────────

function ImageLightbox({ src, title, description, onClose }: {
  src: string; title: string; description?: string; onClose: () => void;
}) {
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
    <div className="fixed inset-0 z-50 flex flex-col bg-black/90 backdrop-blur-sm">
      {/* Controls row */}
      <div className="flex items-center gap-2 px-4 py-3 shrink-0">
        <p className="flex-1 text-white/60 text-sm truncate">{title}</p>
        <button onClick={() => setZoom(z => Math.max(0.5, z - 0.3))}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <span className="text-sm font-bold">−</span>
        </button>
        <span className="text-white/40 text-xs w-10 text-center">{Math.round(zoom * 100)}%</span>
        <button onClick={() => setZoom(z => Math.min(4, z + 0.3))}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <span className="text-sm font-bold">+</span>
        </button>
        <a href={src} download="educational-diagram.png"
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <Download size={15} />
        </a>
        <button onClick={onClose}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <X size={15} />
        </button>
      </div>

      {/* Scrollable content — image + full description */}
      <div className="flex-1 overflow-y-auto" onClick={onClose}>
        <div className="flex flex-col items-center gap-6 px-4 py-6 max-w-3xl mx-auto"
          onClick={e => e.stopPropagation()}>
          <img src={src} alt={title}
            style={{ transform: `scale(${zoom})`, transition: 'transform 0.15s ease', transformOrigin: 'top center' }}
            className="max-w-full max-h-[60vh] object-contain rounded-xl select-none cursor-zoom-in bg-white"
            onClick={() => setZoom(z => z === 1 ? 2 : 1)}
            draggable={false} />
          {description && (
            <div className="w-full bg-white/5 border border-white/10 rounded-xl px-5 py-4 text-left">
              <p className="text-white/40 text-[10px] uppercase tracking-wide font-medium mb-2">About this diagram</p>
              <p className="text-white/85 text-sm leading-relaxed whitespace-pre-wrap">{description}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ImageCard
// ─────────────────────────────────────────────────────────────────────────────

function ImageCard({ job, onClick, onGoToChat, onRemove }: {
  job: EduImageJob; onClick: () => void;
  onGoToChat?: () => void; onRemove?: (id: string) => void;
}) {
  const { token } = useSessionStore();
  const { t } = useTranslation();
  const { badge, gradient } = domainStyle(job.domain);
  const score = job.critic_report?.score;
  const scoreColor = score == null ? '' : score >= 85 ? 'bg-emerald-500/80' : score >= 70 ? 'bg-amber-500/80' : 'bg-red-500/80';

  function formatRelDate(iso: string): string {
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    if (diff === 0) return t.sidebar.today;
    if (diff === 1) return t.sidebar.yesterday;
    if (diff < 7)  return t.studySets.daysAgo.replace('{n}', String(diff));
    return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric' });
  }

  const date = job.created_at ? formatRelDate(job.created_at) : '';
  const [deleting, setDeleting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [showInfo, setShowInfo] = useState(false);

  useEffect(() => {
    if (!showInfo) return;
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setShowInfo(false); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showInfo]);

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
    <>
    <div onClick={job.status === 'ready' ? onClick : undefined}
      className={`group bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden
                  transition-all duration-200 flex flex-col
                  ${job.status === 'ready'
                    ? 'cursor-pointer hover:border-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/8'
                    : ''}`}>
      <div className={`aspect-video relative overflow-hidden bg-gradient-to-br ${gradient} shrink-0`}>
        {job.image_url ? (
          <img src={job.image_url} alt={job.concept} className="w-full h-full object-contain bg-white" />
        ) : job.status === 'processing' ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <Loader2 size={28} className="text-white/40 animate-spin" />
            <p className="text-white/30 text-[10px]">{t.images.generatingBtn}</p>
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <AlertCircle size={24} className="text-red-400/60" />
            <p className="text-white/30 text-[10px]">{t.studySets.statusFailed}</p>
          </div>
        )}
        {job.status === 'ready' && (
          <div className="absolute inset-0 flex items-center justify-center
                          opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full
                            flex items-center justify-center ring-1 ring-white/30">
              <ZoomIn size={20} className="text-white" />
            </div>
          </div>
        )}
        {score != null && (
          <div className={`absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-white text-[10px]
                           font-semibold leading-none ${scoreColor} backdrop-blur-sm`}>
            {score}/100
          </div>
        )}
      </div>
      <div className="p-3 flex flex-col gap-2 flex-1">
        <div className="min-h-[2.5rem] space-y-1">
          <p className="text-[var(--tx1)] text-sm font-medium line-clamp-2 leading-snug" title={job.concept}>
            {job.concept}
          </p>
          {job.description && (
            <p className="text-[var(--tx5)] text-xs line-clamp-2 leading-snug">
              {job.description}
            </p>
          )}
        </div>
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
            {job.description && (
              <button onClick={e => { e.stopPropagation(); setShowInfo(true); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                title={t.images.aboutDiagram}>
                <FileText size={13} />
              </button>
            )}
            {onGoToChat && job.status === 'ready' && (
              <button onClick={e => { e.stopPropagation(); onGoToChat(); }}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
                title="Go to chat message">
                <MessageSquare size={13} />
              </button>
            )}
            {job.status === 'failed' && (
              <button onClick={handleRetry} disabled={retrying}
                className="w-7 h-7 flex items-center justify-center rounded-lg
                           text-[var(--tx5)] hover:text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                title={t.images.tryAgain}>
                <RefreshCw size={13} className={retrying ? 'animate-spin' : ''} />
              </button>
            )}
            <button onClick={handleDelete} disabled={deleting}
              className="w-7 h-7 flex items-center justify-center rounded-lg
                         text-[var(--tx5)] hover:text-red-400 hover:bg-red-500/10 transition-colors"
              title={t.delete}>
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>

    {showInfo && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        onClick={e => { e.stopPropagation(); if (e.target === e.currentTarget) setShowInfo(false); }}
      >
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl
                        w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl shadow-black/40"
          onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)] shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-indigo-600/20 flex items-center justify-center">
                <FileText size={13} className="text-indigo-400" />
              </div>
              <h2 className="text-[var(--tx1)] font-semibold text-sm">{t.images.aboutDiagram}</h2>
            </div>
            <button onClick={() => setShowInfo(false)}
              className="w-7 h-7 flex items-center justify-center rounded-lg
                         text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors"
              aria-label={t.close}>
              <X size={15} />
            </button>
          </div>
          <div className="flex-1 min-h-0 chat-scroll px-6 py-5 space-y-4">
            {job.image_url && (
              <img src={job.image_url} alt={job.concept}
                className="w-full max-h-48 object-contain rounded-xl bg-white border border-[var(--bd)]" />
            )}
            <div className="space-y-1.5">
              <p className="text-[var(--tx1)] font-semibold text-sm">{job.concept}</p>
              {(job.domain || date) && (
                <div className="flex items-center gap-2">
                  {job.domain && (
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium capitalize border ${badge}`}>
                      {job.domain}
                    </span>
                  )}
                  {date && <span className="text-[var(--tx6)] text-xs">{date}</span>}
                </div>
              )}
            </div>
            <div className="ai-content text-sm leading-relaxed text-[var(--tx2)]">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}>
                {preprocessMath(job.description ?? '')}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DiagramsTabContent — images generator & gallery (inner content, no sidebar)
// ─────────────────────────────────────────────────────────────────────────────

function DiagramsTabContent() {
  const router = useRouter();
  const { user, token, sessionId } = useSessionStore();
  const { t } = useTranslation();
  const { requireAuth, showGate, closeGate } = useAuthGuard();
  const [concept, setConcept]   = useState('');
  const [jobId,   setJobId]     = useState<string | null>(null);
  const [current, setCurrent]   = useState<EduImageJob | null>(null);
  const [history, setHistory]   = useState<EduImageJob[]>([]);
  const [histLoading, setHistLoading] = useState(false);
  const [lightbox, setLightbox] = useState<EduImageJob | null>(null);
  const pollRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setHistLoading(true);
    listEduImages({ user_id: user?.id, session_id: sessionId ?? undefined }, token ?? undefined)
      .then(r => { setHistory(r); setHistLoading(false); })
      .catch(() => setHistLoading(false));
  }, [user?.id, sessionId]);

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
    <>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 sm:px-6 py-4 border-b border-[var(--bd)] shrink-0">
        <div className="flex-1 min-w-0">
          <h1 className="text-[var(--tx1)] font-semibold">{t.images.title}</h1>
          <p className="text-[var(--tx6)] text-xs mt-0.5">{t.images.subtitle}</p>
        </div>
        <button onClick={() => window.dispatchEvent(new CustomEvent('start-images-tour'))}
          className="text-[var(--tx7)] hover:text-indigo-400 transition-colors p-1"
          title="Take a tour">
          <HelpCircle size={13} />
        </button>
      </div>

      <div className="flex-1 chat-scroll">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-8">
          {/* Generator input */}
          <div className="space-y-3">
            <div className="relative">
              <textarea data-tour="image-input" ref={inputRef}
                value={concept} onChange={e => setConcept(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); requireAuth(handleGenerate); } }}
                placeholder={t.images.inputPlaceholder} rows={2} disabled={isGenerating}
                className="w-full px-4 py-3.5 pr-24 rounded-2xl bg-[var(--surface)] border border-[var(--bd)]
                           text-[var(--tx1)] text-sm placeholder-[var(--tx7)] resize-none
                           focus:outline-none focus:border-indigo-500/50 disabled:opacity-60 transition-colors
                           leading-relaxed" />
              {showGate && <SignupModal reason="feature_gate" onClose={closeGate} />}
              <button onClick={() => requireAuth(handleGenerate)} disabled={!concept.trim() || isGenerating}
                className="absolute right-3 bottom-3 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold
                           bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white transition-colors">
                {isGenerating ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                {isGenerating ? t.images.generatingBtn : t.images.generateBtn}
              </button>
            </div>
            <div data-tour="image-examples" className="flex flex-wrap gap-1.5">
              {t.images.examples.slice(0, 5).map(ex => (
                <button key={ex} onClick={() => { setConcept(ex); inputRef.current?.focus(); }}
                  className="text-[10px] px-2.5 py-1 rounded-full bg-[var(--ov3)] hover:bg-[var(--ov4)]
                             text-[var(--tx5)] hover:text-[var(--tx2)] border border-[var(--bd)]
                             transition-colors truncate max-w-[180px]">
                  {ex}
                </button>
              ))}
            </div>
          </div>

          {/* Current result */}
          {current && (
            <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] overflow-hidden">
              <div className="flex items-center gap-3 px-5 py-3 border-b border-[var(--bd)]">
                <DomainBadge domain={current.domain} />
                <p className="text-[var(--tx3)] text-sm flex-1 truncate">{current.concept}</p>
                {current.status === 'processing' && (
                  <span className="text-[11px] text-yellow-400 flex items-center gap-1.5 shrink-0">
                    <Loader2 size={11} className="animate-spin" /> {t.images.processing}
                  </span>
                )}
                {current.status === 'ready' && (
                  <div className="flex items-center gap-1.5 shrink-0">
                    <a href={current.image_url!} download="educational-diagram.png"
                      className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg
                                 bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx4)]
                                 border border-[var(--bd)] transition-colors">
                      <Download size={11} /> {t.images.save}
                    </a>
                    <button onClick={() => { setConcept(current.concept); inputRef.current?.focus(); }}
                      className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg
                                 bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx4)]
                                 border border-[var(--bd)] transition-colors">
                      <RefreshCw size={11} /> {t.images.reGenerate}
                    </button>
                  </div>
                )}
              </div>
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
                    <p className="text-[var(--tx3)] text-sm font-medium">{t.images.creating}</p>
                    <p className="text-[var(--tx6)] text-xs mt-1">{t.images.creatingSteps}</p>
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
                  <p className="text-red-400 text-sm">{t.images.failedTitle}</p>
                  <p className="text-[var(--tx6)] text-xs max-w-sm text-center">{current.error_msg}</p>
                  <button onClick={() => { setConcept(current.concept); handleGenerate(); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium
                               bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx3)] border border-[var(--bd)] transition-colors">
                    <RefreshCw size={11} /> {t.images.tryAgain}
                  </button>
                </div>
              ) : null}

              {current.status === 'ready' && current.description && (
                <div className="px-5 py-4 border-t border-[var(--bd)] bg-[var(--surface)]">
                  <p className="text-[var(--tx6)] text-[10px] uppercase tracking-wide font-medium mb-2">{t.images.aboutDiagram}</p>
                  <div className="text-[var(--tx3)] text-sm leading-relaxed space-y-2 whitespace-pre-wrap">
                    {current.description}
                  </div>
                </div>
              )}

              {current.status === 'ready' && (
                <div className="px-5 py-3 border-t border-[var(--bd)] bg-[var(--ov2)] space-y-2.5">
                  {current.knowledge_model?.learning_goal && (
                    <p className="text-[var(--tx5)] text-xs leading-snug">
                      <span className="text-[var(--tx7)] font-medium">{t.images.goal}</span>
                      {current.knowledge_model.learning_goal}
                    </p>
                  )}
                  {(current.spec?.visual_elements ?? current.knowledge_model?.must_show ?? []).length > 0 && (
                    <div>
                      <p className="text-[var(--tx7)] text-[10px] uppercase tracking-wide font-medium mb-1">{t.images.shows}</p>
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
                  {current.critic_report?.score != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-[var(--tx7)] text-[10px] uppercase tracking-wide font-medium">{t.images.qualityScore}</span>
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

          {/* Past images gallery */}
          {(history.length > 0 || histLoading) && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Clock size={13} className="text-[var(--tx6)]" />
                <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">
                  {t.images.pastDiagrams}
                </p>
              </div>
              {histLoading ? (
                <div className="flex items-center justify-center py-8 gap-2 text-[var(--tx6)] text-sm">
                  <Loader2 size={14} className="animate-spin" /> {t.loading}
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {history.map((job, i) => (
                    <ImageCard key={job.id ?? job.jobId ?? i} job={job}
                      onClick={() => job.image_url ? setLightbox(job) : undefined}
                      onGoToChat={job.conversation_id
                        ? () => router.push(`/?conv=${job.conversation_id}${job.message_id ? `&msg=${job.message_id}` : ''}`)
                        : undefined}
                      onRemove={id => setHistory(prev => prev.filter(h => h.id !== id))} />
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
                <p className="text-[var(--tx2)] font-medium">{t.images.emptyTitle}</p>
                <p className="text-[var(--tx6)] text-sm mt-1 max-w-xs">{t.images.emptyDesc}</p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-w-md">
                {t.images.examples.slice(5).map(ex => (
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

      {lightbox && (
        <ImageLightbox src={lightbox.image_url!} title={lightbox.concept}
          description={lightbox.description} onClose={() => setLightbox(null)} />
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VideosTabContent — video generator, library, and detail view (inner, no sidebar)
// ─────────────────────────────────────────────────────────────────────────────

function VideosTabContent({ videoId }: { videoId: number | null }) {
  const router  = useRouter();
  const { t }   = useTranslation();
  const { language } = useLanguageStore();
  const { token, user, sessionId, setActiveConversationId } = useSessionStore();
  const { requireAuth: requireAuthVideo, showGate: showVideoGate, closeGate: closeVideoGate } = useAuthGuard();

  const STEPS = [
    t.video.writingScript,
    t.video.generatingAnimation,
    t.video.queuedRendering,
    t.video.renderingVideo,
  ];

  // Detail view state
  const [status,      setStatus]      = useState('pending');
  const [videoUrl,    setVideoUrl]    = useState<string | null>(null);
  const [error,       setError]       = useState<string | null>(null);
  const [stepIdx,     setStepIdx]     = useState(0);
  const [transcript,  setTranscript]  = useState<string | null>(null);
  const [qualityTier, setQualityTier] = useState<string | null>(null);
  const [retrying,        setRetrying]        = useState(false);
  const [showModal,       setShowModal]       = useState(false);
  const [modalText,       setModalText]       = useState<string>('');
  const [showFeedback,    setShowFeedback]    = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [retryTick,   setRetryTick]   = useState(0);

  // Videos list (both views)
  const [videos,        setVideos]        = useState<VideoItem[]>([]);
  const [videosLoading, setVideosLoading] = useState(true);

  // Library view state
  const [genTopic,   setGenTopic]   = useState('');
  const [generating, setGenerating] = useState(false);
  const [genError,   setGenError]   = useState<string | null>(null);

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
        if (data.quality_tier) setQualityTier(data.quality_tier);
        if (DONE_STATUSES.has(data.status)) { setVideoUrl(data.video_url ?? null); return; }
        if (data.status === 'failed')       { setError(data.error_message ?? t.errors.videoFailed); return; }
        setStepIdx(statusToStepIdx(data.status));
        setTimeout(poll, 4000);
      } catch { if (!stopped) setError(t.errors.generic); }
    }
    poll();
    return () => { stopped = true; };
  }, [videoId, retryTick]);

  // Load videos list
  useEffect(() => {
    setVideosLoading(true);
    const load = user?.id
      ? getUserVideos(user.id, token ?? undefined)
      : sessionId ? getSessionVideos(sessionId) : Promise.resolve([]);
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

  async function handleRetryFromLibrary(vid: number) {
    setVideos(prev => prev.map(v => v.id === vid ? { ...v, status: 'pending' } : v));
    try {
      await retryVideo(vid, token ?? undefined);
      router.push(`/assets?id=${vid}`);
    } catch { refreshList(); }
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
      router.push(`/assets?id=${res.video_id}`);
    } catch (e: any) {
      const isLimit = e?.message === 'session_limit_reached' || e?.message === 'Daily video limit reached';
      setGenError(isLimit
        ? '⚠️ Daily video limit reached. Come back tomorrow or upgrade your plan.'
        : (e?.message ?? 'Generation failed. Please try again.'));
    } finally { setGenerating(false); }
  }

  async function handleRetry() {
    if (!videoId) return;
    setRetrying(true);
    setError(null);
    setStatus('pending');
    setStepIdx(0);
    setVideoUrl(null);
    try {
      await retryVideo(videoId, token ?? undefined);
      refreshList();
      setRetryTick(n => n + 1);
    } catch (e: any) {
      setError(e.message ?? 'Retry failed');
    } finally { setRetrying(false); }
  }

  async function handleImprove(feedback: string) {
    if (!videoId || !feedback.trim()) return;
    setFeedbackLoading(true);
    try {
      await improveVideo(videoId, feedback, token ?? undefined);
      setShowFeedback(false);
      setStatus('pending');
      setStepIdx(0);
      setVideoUrl(null);
      setError(null);
      refreshList();
      setRetryTick(n => n + 1);
    } catch (e: any) {
      setError(e.message ?? 'Improvement failed. Please try again.');
      setShowFeedback(false);
    } finally { setFeedbackLoading(false); }
  }

  const isLoading = LOADING_STATUSES.has(status);
  const isDone    = DONE_STATUSES.has(status);
  const isFailed  = status === 'failed';

  // ── Library view ─────────────────────────────────────────────────────────
  if (!videoId) {
    const EXAMPLES = t.video.examples;
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-[var(--bd)] shrink-0">
          <div className="flex-1 min-w-0">
            <h1 className="text-[var(--tx1)] font-semibold">{t.video.studio}</h1>
            <p className="text-[var(--tx6)] text-xs mt-0.5">{t.video.studioDesc}</p>
          </div>
          <button onClick={() => window.dispatchEvent(new CustomEvent('start-videos-tour'))}
            className="flex items-center gap-1 text-[11px] text-[var(--tx7)] hover:text-purple-400 transition-colors px-2 py-1"
            title="Take a tour">
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
            <div className="space-y-3">
              <div className="relative">
                <textarea data-tour="video-input"
                  value={genTopic} onChange={e => setGenTopic(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); requireAuthVideo(handleGenerate); } }}
                  placeholder={t.video.generatePlaceholder} rows={2} disabled={generating}
                  className="w-full px-4 py-3.5 pr-28 rounded-2xl bg-[var(--surface)] border border-[var(--bd)]
                             text-[var(--tx1)] text-sm placeholder-[var(--tx7)] resize-none
                             focus:outline-none focus:border-purple-500/50 disabled:opacity-60 transition-colors
                             leading-relaxed" />
                {showVideoGate && <SignupModal reason="feature_gate" onClose={closeVideoGate} />}
                <button onClick={() => requireAuthVideo(handleGenerate)} disabled={!genTopic.trim() || generating}
                  className="absolute right-3 bottom-3 flex items-center gap-1.5 px-3 py-1.5 rounded-xl
                             text-xs font-semibold bg-purple-600 hover:bg-purple-500
                             disabled:opacity-40 text-white transition-colors">
                  {generating ? <Loader size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  {generating ? t.video.generatingBtn : t.video.generateBtn}
                </button>
              </div>
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
              {(() => {
                const hasCompleted = videos.some(v => v.status === 'complete' || v.status === 'completed');
                if (!user) return (
                  <div className="flex items-center gap-2 text-xs">
                    <QualityBadge tier="standard" />
                    <button onClick={() => router.push('/login')}
                      className="text-purple-400 hover:text-purple-300 underline underline-offset-2 transition-colors">
                      Sign in for Enhanced quality →
                    </button>
                  </div>
                );
                if (user.tier === 'pro') return <div className="flex items-center gap-2 text-xs"><QualityBadge tier="premium" /></div>;
                if (!hasCompleted) return (
                  <div className="flex items-center gap-2 text-xs">
                    <QualityBadge tier="premium" />
                    <span className="text-[var(--tx7)]">First video gift</span>
                  </div>
                );
                return <div className="flex items-center gap-2 text-xs"><QualityBadge tier="enhanced" /></div>;
              })()}
              {genError && (
                <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
                  {genError}
                </p>
              )}
            </div>
            <VideoLibraryGrid
              videos={videos} loading={videosLoading}
              onTranscript={openTranscript} onGoToConversation={handleGoToConversation}
              onRetry={handleRetryFromLibrary} embedded
              emptyEmbeddedTitle={t.video.noCompletedYet}
              emptyEmbeddedDesc={t.video.generatePlaceholder}
              pastVideosLabel={t.video.pastVideos} />
          </div>
        </div>
        {showModal && modalText && <TranscriptModal markdown={modalText} onClose={closeModal} />}
      </div>
    );
  }

  // ── Detail view ───────────────────────────────────────────────────────────
  return (
    <>
      <div className="flex-1 flex flex-col overflow-hidden">
        <MobileTopBar />
        <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--bd)] shrink-0">
          <button onClick={() => router.push('/assets')}
            className="text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors" aria-label="Back">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-[var(--tx1)] font-semibold flex-1">
            {isDone ? t.video.ready : isFailed ? t.video.failed : t.video.generating}
          </h1>
        </div>
        <div className="flex-1 chat-scroll">
          <div className="flex items-start justify-center px-3 sm:px-6 py-6 sm:py-10 min-h-full">
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
                <p className="text-[var(--tx5)] text-sm mb-4">{t.video.generatingDesc}</p>
                {qualityTier && <div className="mb-6 text-left"><QualityBanner tier={qualityTier} /></div>}
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
                        }`}>{step}</span>
                      </div>
                    );
                  })}
                </div>
                {transcript && <div className="mt-8"><TranscriptButton onClick={() => openTranscript(transcript)} /></div>}
              </div>
            )}

            {isDone && videoUrl && (
              <div className="w-full max-w-3xl">
                <div className="aspect-video rounded-2xl overflow-hidden bg-black
                                shadow-2xl shadow-purple-500/10 mb-3">
                  <video src={videoUrl} controls autoPlay controlsList="nodownload" disablePictureInPicture
                    className="w-full h-full" onContextMenu={e => e.preventDefault()} />
                </div>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[var(--tx5)] text-sm min-w-0 flex items-center gap-2 truncate">
                    ✅ {t.video.ready}
                    {qualityTier && <QualityBadge tier={qualityTier} />}
                  </p>
                  <div className="flex items-center gap-2 shrink-0">
                    {transcript && (
                      <button onClick={() => openTranscript(transcript)} title={t.video.solutionTranscript}
                        className="flex items-center gap-2 px-3 sm:px-4 py-2
                                   bg-[var(--ov3)] hover:bg-[var(--ov4)]
                                   rounded-xl text-[var(--tx2)] text-sm transition-colors">
                        <FileText size={14} />
                        <span className="hidden sm:inline">{t.video.solutionTranscript}</span>
                      </button>
                    )}
                    <button onClick={() => setShowFeedback(true)} title="Improve this video"
                      className="flex items-center gap-2 px-3 sm:px-4 py-2
                                 bg-[var(--ov3)] hover:bg-orange-500/15
                                 hover:text-orange-400 hover:border-orange-500/30
                                 border border-transparent
                                 rounded-xl text-[var(--tx5)] text-sm transition-colors">
                      <ThumbsDown size={14} />
                      <span className="hidden sm:inline">Improve</span>
                    </button>
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

            {isFailed && (
              <div className="text-center max-w-md flex flex-col items-center gap-5">
                <XCircle size={48} className="text-red-400" />
                <h2 className="text-[var(--tx1)] font-semibold">{t.video.failed}</h2>
                {error && <p className="text-[var(--tx5)] text-sm">{error}</p>}
                <div className="flex gap-3 flex-wrap justify-center">
                  <button onClick={handleRetry} disabled={retrying}
                    title={retrying ? t.video.retrying : transcript ? t.video.retryBtn : t.video.regenerateBtn}
                    className="flex items-center gap-2 px-4 sm:px-5 py-2.5
                               bg-purple-600 hover:bg-purple-500
                               disabled:opacity-50 text-white text-sm rounded-xl transition-colors">
                    <RefreshCw size={14} className={retrying ? 'animate-spin' : ''} />
                    <span className="hidden sm:inline">
                      {retrying ? t.video.retrying : transcript ? t.video.retryBtn : t.video.regenerateBtn}
                    </span>
                  </button>
                  <button onClick={() => router.push('/assets')} title={t.back}
                    className="flex items-center gap-2 px-4 sm:px-5 py-2.5
                               bg-[var(--ov3)] hover:bg-[var(--ov4)]
                               text-[var(--tx2)] text-sm rounded-xl transition-colors">
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

      {/* Right sidebar: video list — desktop only */}
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
              <VideoSidebarCard key={v.id} v={v}
                active={v.id === videoId}
                onClick={() => router.push(`/assets?id=${v.id}`)} />
            ))}
          </div>
        )}
      </aside>

      {showModal && modalText && <TranscriptModal markdown={modalText} onClose={closeModal} />}
      {showFeedback && (
        <FeedbackModal loading={feedbackLoading}
          onClose={() => setShowFeedback(false)} onSubmit={handleImprove} />
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AssetsContent — unified shell with sidebar and tab switcher
// ─────────────────────────────────────────────────────────────────────────────

function AssetsContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();

  const rawId  = searchParams.get('id');
  const videoId = rawId ? Number(rawId) : null;
  const rawTab  = searchParams.get('tab');
  const activeTab = rawTab === 'diagrams' ? 'diagrams' : 'videos';

  // In detail view the main area is a flex row (left panel + right aside).
  // In library/diagrams view it's a flex column.
  const isDetailView = !!videoId;

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <div className={`flex-1 flex min-w-0 overflow-hidden ${isDetailView ? '' : 'flex-col'}`}>
        <VideosTour />
        <ImagesTour />

        {/* Tab bar + MobileTopBar: only shown in library/diagrams view */}
        {!isDetailView && (
          <>
            <MobileTopBar />
            <div className="flex items-center gap-1 px-3 border-b border-[var(--bd)] shrink-0">
              <Link
                href="/assets"
                replace
                prefetch={false}
                className={`flex items-center gap-1.5 px-3 py-3 text-xs font-medium border-b-2 transition-colors
                  ${activeTab === 'videos'
                    ? 'border-purple-500 text-purple-400'
                    : 'border-transparent text-[var(--tx5)] hover:text-[var(--tx2)]'}`}>
                <Video size={13} /> Videos
              </Link>
              <Link
                href="/assets?tab=diagrams"
                replace
                prefetch={false}
                className={`flex items-center gap-1.5 px-3 py-3 text-xs font-medium border-b-2 transition-colors
                  ${activeTab === 'diagrams'
                    ? 'border-indigo-500 text-indigo-400'
                    : 'border-transparent text-[var(--tx5)] hover:text-[var(--tx2)]'}`}>
                <Sparkles size={13} /> Diagrams
              </Link>
            </div>
          </>
        )}

        {/* Tab content */}
        {(isDetailView || activeTab === 'videos') ? (
          <VideosTabContent videoId={videoId} />
        ) : (
          <DiagramsTabContent />
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page export
// ─────────────────────────────────────────────────────────────────────────────

export default function AssetsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <AssetsContent />
    </Suspense>
  );
}
