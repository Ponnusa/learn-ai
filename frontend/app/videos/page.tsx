'use client';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Download, CheckCircle, XCircle, Loader,
  RefreshCw, BookOpen, ChevronDown, ChevronUp,
} from 'lucide-react';
import { getVideoStatus, retryVideoManim, getUserVideos } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import { Sidebar } from '@/components/layout/Sidebar';

const STEPS = [
  'Writing solution & script',
  'Planning animation',
  'Generating Manim code',
  'Rendering video',
];

// ── Transcript panel ──────────────────────────────────────────────────────────
function TranscriptPanel({ markdown }: { markdown: string }) {
  const [open, setOpen] = useState(false);
  if (!markdown) return null;
  return (
    <div className="w-full max-w-2xl mt-6 rounded-2xl border border-[var(--bd)] overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3 bg-[var(--ov3)] hover:bg-[var(--ov4)] transition-colors text-left"
      >
        <span className="flex items-center gap-2 text-[var(--tx2)] text-sm font-medium">
          <BookOpen size={15} />
          Solution &amp; Transcript
        </span>
        {open ? <ChevronUp size={15} className="text-[var(--tx5)]" /> : <ChevronDown size={15} className="text-[var(--tx5)]" />}
      </button>
      {open && (
        <div className="px-5 py-4 text-[var(--tx3)] text-sm leading-relaxed whitespace-pre-wrap bg-[var(--bg2)] border-t border-[var(--bd)] max-h-96 overflow-y-auto no-scrollbar">
          {markdown}
        </div>
      )}
    </div>
  );
}

// ── User video list ───────────────────────────────────────────────────────────
function UserVideoCard({ v, onClick }: { v: any; onClick: () => void }) {
  const statusColor: Record<string, string> = {
    completed: 'text-green-400', complete: 'text-green-400',
    failed: 'text-red-400',
    queued: 'text-yellow-400', rendering: 'text-yellow-400',
    pending: 'text-[var(--tx5)]', transcript_ready: 'text-blue-400',
  };
  const dot = statusColor[v.status] ?? 'text-[var(--tx5)]';
  return (
    <button
      onClick={onClick}
      className="w-full text-left flex gap-3 px-4 py-3 rounded-xl hover:bg-[var(--ov3)] transition-colors group"
    >
      {v.video_url ? (
        <video src={v.video_url} className="w-24 h-14 rounded-lg object-cover flex-shrink-0 bg-black" muted />
      ) : (
        <div className="w-24 h-14 rounded-lg bg-[var(--ov3)] flex items-center justify-center flex-shrink-0">
          <Loader size={16} className="text-[var(--tx5)]" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-[var(--tx2)] text-sm font-medium truncate">{v.prompt || 'Untitled'}</p>
        <p className="text-[var(--tx5)] text-xs mt-0.5 capitalize">
          <span className={dot}>●</span>&nbsp;{v.status}
          {v.subject ? ` · ${v.subject}` : ''}
        </p>
        {v.transcript_markdown && (
          <p className="text-[var(--tx6)] text-xs mt-0.5 truncate">{v.transcript_markdown.slice(0, 80)}…</p>
        )}
      </div>
    </button>
  );
}

// ── Main content ──────────────────────────────────────────────────────────────
function VideosContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const { t }        = useTranslation();
  const { token, user } = useSessionStore();

  const videoId = searchParams.get('id') ? Number(searchParams.get('id')) : null;
  const [status,     setStatus]     = useState('pending');
  const [videoUrl,   setVideoUrl]   = useState<string | null>(null);
  const [error,      setError]      = useState<string | null>(null);
  const [stepIdx,    setStepIdx]    = useState(0);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [retrying,   setRetrying]   = useState(false);
  const [userVideos, setUserVideos] = useState<any[]>([]);
  const [showList,   setShowList]   = useState(false);

  // Poll current video
  useEffect(() => {
    if (!videoId) return;
    let stopped = false;

    async function poll() {
      try {
        const data = await getVideoStatus(videoId!, token ?? undefined);
        if (stopped) return;
        setStatus(data.status);
        if (data.transcript_markdown) setTranscript(data.transcript_markdown);

        const done    = data.status === 'complete' || data.status === 'completed';
        const failed  = data.status === 'failed';

        if (done) { setVideoUrl(data.video_url ?? null); return; }
        if (failed) { setError(data.error_message ?? t.errors.videoFailed); return; }

        // Still in progress — advance step indicator
        setStepIdx(prev => (prev + 1) % STEPS.length);
        setTimeout(poll, 4000);
      } catch {
        if (!stopped) setError(t.errors.generic);
      }
    }

    poll();
    return () => { stopped = true; };
  }, [videoId]);

  // Load user video list
  useEffect(() => {
    if (!user?.id) return;
    getUserVideos(user.id, token ?? undefined)
      .then(setUserVideos)
      .catch(() => {});
  }, [user?.id]);

  async function handleRetry() {
    if (!videoId) return;
    setRetrying(true);
    setError(null);
    setStatus('pending');
    setStepIdx(0);
    try {
      await retryVideoManim(videoId, token ?? undefined);
      // Restart polling
      setTimeout(() => window.location.reload(), 500);
    } catch (e: any) {
      setError(e.message ?? 'Retry failed');
      setRetrying(false);
    }
  }

  const isLoading = ['pending', 'queued', 'transcript_ready', 'rendering'].includes(status);
  const isDone    = status === 'complete' || status === 'completed';
  const isFailed  = status === 'failed';

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex flex-col min-w-0 bg-[var(--bg)]">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--bd)] shrink-0">
          <button onClick={() => router.push('/')} className="text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-[var(--tx1)] font-semibold flex-1">
            {isDone ? t.video.ready : isFailed ? t.video.failed : t.video.generating}
          </h1>

          {/* My videos toggle */}
          {userVideos.length > 0 && (
            <button
              onClick={() => setShowList(s => !s)}
              className="text-xs text-[var(--tx5)] hover:text-[var(--tx2)] transition-colors px-3 py-1.5 rounded-lg hover:bg-[var(--ov3)]"
            >
              My Videos ({userVideos.length})
            </button>
          )}
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Video panel */}
          <div className="flex-1 flex items-center justify-center px-4 py-12 overflow-y-auto no-scrollbar">

            {!videoId && (
              <p className="text-[var(--tx5)]">No video ID provided.</p>
            )}

            {/* Loading state */}
            {videoId && isLoading && (
              <div className="text-center max-w-sm w-full flex flex-col items-center">
                <div className="w-20 h-20 mx-auto mb-8 relative">
                  <div className="w-20 h-20 rounded-full border-4 border-[var(--bd)]" />
                  <div className="w-20 h-20 rounded-full border-4 border-purple-500 border-t-transparent absolute inset-0 animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <img src="/logo-36.png" alt="Learn-AI" className="w-9 h-9 object-contain" />
                  </div>
                </div>
                <h2 className="text-[var(--tx1)] text-xl font-semibold mb-2">{t.video.generating}</h2>
                <p className="text-[var(--tx5)] text-sm mb-8">{t.video.generatingDesc}</p>
                <div className="space-y-3 text-left w-full">
                  {STEPS.map((step, i) => {
                    const done   = i < stepIdx;
                    const active = i === stepIdx;
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${
                          done   ? 'bg-green-500' :
                          active ? 'bg-purple-500 animate-pulse' :
                                   'bg-[var(--ov3)]'
                        }`}>
                          {done   && <CheckCircle size={12} className="text-white" />}
                          {active && <Loader size={10} className="text-white animate-spin" />}
                        </div>
                        <span className={`text-sm transition-colors ${
                          done   ? 'text-[var(--tx6)] line-through' :
                          active ? 'text-[var(--tx1)]' :
                                   'text-[var(--tx9)]'
                        }`}>
                          {step}
                        </span>
                      </div>
                    );
                  })}
                </div>
                {/* Show transcript while video renders */}
                {transcript && <TranscriptPanel markdown={transcript} />}
              </div>
            )}

            {/* Done — video player */}
            {videoId && isDone && videoUrl && (
              <div className="w-full max-w-3xl flex flex-col items-center">
                <div className="aspect-video rounded-2xl overflow-hidden bg-black shadow-2xl shadow-purple-500/10 mb-4 w-full">
                  <video src={videoUrl} controls autoPlay className="w-full h-full" />
                </div>
                <div className="flex items-center justify-between w-full mb-4">
                  <p className="text-[var(--tx5)] text-sm">✅ {t.video.ready}</p>
                  <a
                    href={videoUrl}
                    download
                    className="flex items-center gap-2 px-4 py-2 bg-[var(--ov3)] hover:bg-[var(--ov4)] rounded-xl text-[var(--tx2)] text-sm transition-colors"
                  >
                    <Download size={14} />
                    {t.download}
                  </a>
                </div>
                {transcript && <TranscriptPanel markdown={transcript} />}
              </div>
            )}

            {videoId && isDone && !videoUrl && (
              <div className="text-center flex flex-col items-center gap-4">
                <CheckCircle size={48} className="text-[var(--green)] mx-auto" />
                <p className="text-[var(--tx1)] font-semibold">Video ready — loading player…</p>
                {transcript && <TranscriptPanel markdown={transcript} />}
              </div>
            )}

            {/* Failed */}
            {videoId && isFailed && (
              <div className="text-center max-w-sm flex flex-col items-center gap-4">
                <XCircle size={48} className="text-[var(--red)] mx-auto" />
                <h2 className="text-[var(--tx1)] font-semibold">{t.video.failed}</h2>
                <p className="text-[var(--tx5)] text-sm">{error ?? t.video.failedDesc}</p>

                <div className="flex gap-3 flex-wrap justify-center">
                  {/* Retry Manim only (keeps transcript) */}
                  {transcript && (
                    <button
                      onClick={handleRetry}
                      disabled={retrying}
                      className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm rounded-xl transition-colors"
                    >
                      <RefreshCw size={14} className={retrying ? 'animate-spin' : ''} />
                      {retrying ? 'Retrying…' : 'Retry Video Generation'}
                    </button>
                  )}
                  <button
                    onClick={() => router.push('/')}
                    className="px-5 py-2.5 bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx2)] text-sm rounded-xl transition-colors"
                  >
                    {t.back}
                  </button>
                </div>

                {/* Always show transcript even on failure */}
                {transcript && <TranscriptPanel markdown={transcript} />}
                {!transcript && (
                  <p className="text-[var(--tx6)] text-xs">
                    Transcript unavailable — try regenerating from the chat.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* My Videos sidebar panel */}
          {showList && userVideos.length > 0 && (
            <aside className="w-72 border-l border-[var(--bd)] flex flex-col overflow-hidden shrink-0">
              <div className="px-4 py-3 border-b border-[var(--bd)]">
                <p className="text-[var(--tx2)] text-sm font-medium">My Videos</p>
              </div>
              <div className="flex-1 overflow-y-auto no-scrollbar py-2 px-2 space-y-1">
                {userVideos.map(v => (
                  <UserVideoCard
                    key={v.id}
                    v={v}
                    onClick={() => router.push(`/videos?id=${v.id}`)}
                  />
                ))}
              </div>
            </aside>
          )}
        </div>
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
