'use client';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Download, CheckCircle, XCircle, Loader,
  RefreshCw, BookOpen, ChevronDown, ChevronUp, Play,
} from 'lucide-react';
import { getVideoStatus, retryVideoManim, getUserVideos, getSessionVideos } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import { Sidebar } from '@/components/layout/Sidebar';

const STEPS = [
  'Writing solution & script',
  'Planning animation',
  'Generating Manim code',
  'Rendering video',
];

const LOADING_STATUSES = new Set(['pending', 'queued', 'transcript_ready', 'rendering']);
const DONE_STATUSES    = new Set(['complete', 'completed']);

// ── Transcript panel ──────────────────────────────────────────────────────────
function TranscriptPanel({ markdown }: { markdown: string }) {
  const [open, setOpen] = useState(false);
  if (!markdown) return null;
  return (
    <div className="w-full rounded-2xl border border-[var(--bd)] overflow-hidden mt-4">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3 bg-[var(--ov3)] hover:bg-[var(--ov4)] transition-colors"
      >
        <span className="flex items-center gap-2 text-[var(--tx2)] text-sm font-medium">
          <BookOpen size={14} />
          Solution &amp; Transcript
        </span>
        {open
          ? <ChevronUp size={14} className="text-[var(--tx5)]" />
          : <ChevronDown size={14} className="text-[var(--tx5)]" />}
      </button>
      {open && (
        <div className="px-5 py-4 text-[var(--tx3)] text-sm leading-relaxed whitespace-pre-wrap
                        bg-[var(--bg2)] border-t border-[var(--bd)] max-h-80 overflow-y-auto no-scrollbar">
          {markdown}
        </div>
      )}
    </div>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: 'text-green-400',  complete: 'text-green-400',
    failed:    'text-red-400',
    queued:    'text-yellow-400', rendering: 'text-yellow-400',
    pending:   'text-[var(--tx5)]',
    transcript_ready: 'text-blue-400',
  };
  return (
    <span className={`text-xs capitalize ${map[status] ?? 'text-[var(--tx5)]'}`}>
      ● {status.replace(/_/g, ' ')}
    </span>
  );
}

// ── Video card in the list ────────────────────────────────────────────────────
function VideoCard({ v, active, onClick }: { v: any; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex gap-3 px-3 py-2.5 rounded-xl transition-colors
        ${active ? 'bg-purple-500/15 border border-purple-500/30' : 'hover:bg-[var(--ov3)] border border-transparent'}`}
    >
      {/* Thumbnail */}
      <div className="w-20 h-12 rounded-lg overflow-hidden bg-[var(--ov3)] flex-shrink-0 flex items-center justify-center">
        {v.video_url
          ? <video src={v.video_url} className="w-full h-full object-cover" muted playsInline />
          : DONE_STATUSES.has(v.status)
            ? <Play size={14} className="text-[var(--tx5)]" />
            : LOADING_STATUSES.has(v.status)
              ? <Loader size={14} className="text-[var(--tx5)] animate-spin" />
              : <XCircle size={14} className="text-red-400" />
        }
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-[var(--tx2)] text-xs font-medium truncate leading-snug">
          {v.prompt || 'Untitled'}
        </p>
        <StatusBadge status={v.status} />
        {v.transcript_markdown && (
          <p className="text-[var(--tx6)] text-xs truncate mt-0.5 leading-snug">
            {v.transcript_markdown.slice(0, 70)}…
          </p>
        )}
      </div>
    </button>
  );
}

// ── Videos list (shown when no videoId, or as side panel) ────────────────────
function VideosList({
  videos, currentId, onSelect, loading,
}: {
  videos: any[]; currentId: number | null; onSelect: (id: number) => void; loading: boolean;
}) {
  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader size={20} className="text-[var(--tx5)] animate-spin" />
    </div>
  );
  if (!videos.length) return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center">
      <p className="text-[var(--tx5)] text-sm">No videos yet.</p>
      <p className="text-[var(--tx6)] text-xs">Generate a video from the chat to see it here.</p>
    </div>
  );
  return (
    <div className="flex-1 overflow-y-auto no-scrollbar py-2 px-2 space-y-1">
      {videos.map(v => (
        <VideoCard key={v.id} v={v} active={v.id === currentId} onClick={() => onSelect(v.id)} />
      ))}
    </div>
  );
}

// ── Main content ──────────────────────────────────────────────────────────────
function VideosContent() {
  const searchParams              = useSearchParams();
  const router                    = useRouter();
  const { t }                     = useTranslation();
  const { token, user, sessionId } = useSessionStore();

  const rawId   = searchParams.get('id');
  const videoId = rawId ? Number(rawId) : null;

  // Current video state
  const [status,     setStatus]     = useState('pending');
  const [videoUrl,   setVideoUrl]   = useState<string | null>(null);
  const [error,      setError]      = useState<string | null>(null);
  const [stepIdx,    setStepIdx]    = useState(0);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [prompt,     setPrompt]     = useState<string | null>(null);
  const [retrying,   setRetrying]   = useState(false);

  // Videos list
  const [videos,       setVideos]       = useState<any[]>([]);
  const [videosLoading, setVideosLoading] = useState(true);

  // ── Poll current video ────────────────────────────────────────────────────
  useEffect(() => {
    if (!videoId) return;
    let stopped = false;

    async function poll() {
      try {
        const data = await getVideoStatus(videoId!, token ?? undefined);
        if (stopped) return;
        setStatus(data.status);
        if (data.transcript_markdown) setTranscript(data.transcript_markdown);
        if (data.prompt)              setPrompt(data.prompt);

        if (DONE_STATUSES.has(data.status))     { setVideoUrl(data.video_url ?? null); return; }
        if (data.status === 'failed')           { setError(data.error_message ?? t.errors.videoFailed); return; }

        setStepIdx(prev => (prev + 1) % STEPS.length);
        setTimeout(poll, 4000);
      } catch {
        if (!stopped) setError(t.errors.generic);
      }
    }

    poll();
    return () => { stopped = true; };
  }, [videoId]);

  // ── Load all videos ───────────────────────────────────────────────────────
  useEffect(() => {
    setVideosLoading(true);
    const load = user?.id
      ? getUserVideos(user.id, token ?? undefined)
      : sessionId
        ? getSessionVideos(sessionId)
        : Promise.resolve([]);

    load
      .then(rows => { setVideos(rows); setVideosLoading(false); })
      .catch(() => setVideosLoading(false));
  }, [user?.id, sessionId]);

  // Also refresh the list after a retry so the status updates
  function refreshVideos() {
    const load = user?.id
      ? getUserVideos(user.id, token ?? undefined)
      : sessionId ? getSessionVideos(sessionId) : Promise.resolve([]);
    load.then(setVideos).catch(() => {});
  }

  // ── Retry handler ─────────────────────────────────────────────────────────
  async function handleRetry() {
    if (!videoId) return;
    setRetrying(true);
    setError(null);
    setStatus('pending');
    setStepIdx(0);
    setVideoUrl(null);
    try {
      await retryVideoManim(videoId, token ?? undefined);
      refreshVideos();
      // Restart polling loop
      let stopped = false;
      async function poll() {
        try {
          const data = await getVideoStatus(videoId!, token ?? undefined);
          if (stopped) return;
          setStatus(data.status);
          if (data.transcript_markdown) setTranscript(data.transcript_markdown);
          if (DONE_STATUSES.has(data.status))   { setVideoUrl(data.video_url ?? null); setRetrying(false); refreshVideos(); return; }
          if (data.status === 'failed')         { setError(data.error_message ?? t.errors.videoFailed); setRetrying(false); return; }
          setStepIdx(prev => (prev + 1) % STEPS.length);
          setTimeout(poll, 4000);
        } catch {
          if (!stopped) { setError(t.errors.generic); setRetrying(false); }
        }
      }
      poll();
      return () => { stopped = true; };
    } catch (e: any) {
      setError(e.message ?? 'Retry failed');
      setRetrying(false);
    }
  }

  const isLoading = LOADING_STATUSES.has(status);
  const isDone    = DONE_STATUSES.has(status);
  const isFailed  = status === 'failed';

  // ── No specific video: show full videos list ──────────────────────────────
  if (!videoId) {
    return (
      <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
        <Sidebar onNewChat={() => router.push('/')} />
        <main className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--bd)] shrink-0">
            <button onClick={() => router.push('/')} className="text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
              <ArrowLeft size={20} />
            </button>
            <h1 className="text-[var(--tx1)] font-semibold">My Videos</h1>
          </div>
          <VideosList
            videos={videos} currentId={null} loading={videosLoading}
            onSelect={id => router.push(`/videos?id=${id}`)}
          />
        </main>
      </div>
    );
  }

  // ── Specific video view + side panel ─────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex min-w-0 overflow-hidden">
        {/* ── Left: current video ── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top bar */}
          <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--bd)] shrink-0">
            <button onClick={() => router.push('/videos')} className="text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
              <ArrowLeft size={20} />
            </button>
            <h1 className="text-[var(--tx1)] font-semibold flex-1">
              {isDone ? t.video.ready : isFailed ? t.video.failed : t.video.generating}
            </h1>
          </div>

          <div className="flex-1 overflow-y-auto no-scrollbar">
            <div className="flex items-start justify-center px-6 py-10 min-h-full">

              {/* Loading */}
              {isLoading && (
                <div className="text-center max-w-sm w-full">
                  <div className="w-20 h-20 mx-auto mb-8 relative">
                    <div className="w-20 h-20 rounded-full border-4 border-[var(--bd)]" />
                    <div className="w-20 h-20 rounded-full border-4 border-purple-500 border-t-transparent absolute inset-0 animate-spin" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <img src="/logo-36.png" alt="Learn-AI" className="w-9 h-9 object-contain" />
                    </div>
                  </div>
                  <h2 className="text-[var(--tx1)] text-xl font-semibold mb-2">{t.video.generating}</h2>
                  <p className="text-[var(--tx5)] text-sm mb-8">{t.video.generatingDesc}</p>
                  <div className="space-y-3 text-left">
                    {STEPS.map((step, i) => {
                      const done   = i < stepIdx;
                      const active = i === stepIdx;
                      return (
                        <div key={i} className="flex items-center gap-3">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${
                            done   ? 'bg-green-500' :
                            active ? 'bg-purple-500 animate-pulse' : 'bg-[var(--ov3)]'
                          }`}>
                            {done   && <CheckCircle size={12} className="text-white" />}
                            {active && <Loader size={10} className="text-white animate-spin" />}
                          </div>
                          <span className={`text-sm transition-colors ${
                            done   ? 'text-[var(--tx6)] line-through' :
                            active ? 'text-[var(--tx1)]' : 'text-[var(--tx9)]'
                          }`}>{step}</span>
                        </div>
                      );
                    })}
                  </div>
                  {transcript && <TranscriptPanel markdown={transcript} />}
                </div>
              )}

              {/* Done — video player */}
              {isDone && videoUrl && (
                <div className="w-full max-w-3xl">
                  <div className="aspect-video rounded-2xl overflow-hidden bg-black shadow-2xl shadow-purple-500/10 mb-4">
                    <video src={videoUrl} controls autoPlay className="w-full h-full" />
                  </div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-[var(--tx5)] text-sm">✅ {t.video.ready}</p>
                    <a href={videoUrl} download
                      className="flex items-center gap-2 px-4 py-2 bg-[var(--ov3)] hover:bg-[var(--ov4)] rounded-xl text-[var(--tx2)] text-sm transition-colors">
                      <Download size={14} /> {t.download}
                    </a>
                  </div>
                  {transcript && <TranscriptPanel markdown={transcript} />}
                </div>
              )}

              {isDone && !videoUrl && (
                <div className="text-center flex flex-col items-center gap-4">
                  <CheckCircle size={48} className="text-green-400" />
                  <p className="text-[var(--tx1)] font-semibold">Video ready — loading player…</p>
                  {transcript && <TranscriptPanel markdown={transcript} />}
                </div>
              )}

              {/* Failed */}
              {isFailed && (
                <div className="text-center max-w-md flex flex-col items-center gap-4">
                  <XCircle size={48} className="text-red-400" />
                  <h2 className="text-[var(--tx1)] font-semibold">{t.video.failed}</h2>

                  {prompt && (
                    <p className="text-[var(--tx5)] text-sm bg-[var(--ov3)] rounded-xl px-4 py-2 w-full text-left">
                      <span className="text-[var(--tx6)] text-xs block mb-1">Topic</span>
                      {prompt}
                    </p>
                  )}

                  {error && (
                    <p className="text-[var(--tx5)] text-sm">{error}</p>
                  )}

                  <div className="flex gap-3 flex-wrap justify-center">
                    {/* Retry always available — endpoint handles whether to reuse transcript or run full pipeline */}
                    <button
                      onClick={handleRetry}
                      disabled={retrying}
                      className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-500
                                 disabled:opacity-50 text-white text-sm rounded-xl transition-colors"
                    >
                      <RefreshCw size={14} className={retrying ? 'animate-spin' : ''} />
                      {retrying ? 'Retrying…' : transcript ? 'Retry Video Generation' : 'Regenerate Video'}
                    </button>

                    <button
                      onClick={() => router.push('/')}
                      className="px-5 py-2.5 bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx2)] text-sm rounded-xl transition-colors"
                    >
                      {t.back}
                    </button>
                  </div>

                  {/* Transcript shown even on failure */}
                  {transcript
                    ? <TranscriptPanel markdown={transcript} />
                    : <p className="text-[var(--tx6)] text-xs">Transcript will be regenerated automatically on retry.</p>
                  }
                </div>
              )}

            </div>
          </div>
        </div>

        {/* ── Right: videos list panel (always visible) ── */}
        <aside className="w-64 border-l border-[var(--bd)] flex flex-col overflow-hidden shrink-0">
          <div className="px-4 py-3 border-b border-[var(--bd)]">
            <p className="text-[var(--tx2)] text-sm font-semibold">My Videos</p>
          </div>
          <VideosList
            videos={videos} currentId={videoId} loading={videosLoading}
            onSelect={id => router.push(`/videos?id=${id}`)}
          />
        </aside>
      </main>
    </div>
  );
}

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
