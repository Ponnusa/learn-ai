'use client';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { ArrowLeft, Download, CheckCircle, XCircle, Loader } from 'lucide-react';
import { getVideoStatus } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';
import { Sidebar } from '@/components/layout/Sidebar';

const STEPS = [
  'Writing solution & script',
  'Planning animation',
  'Generating Manim code',
  'Rendering video',
];

function VideosContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const { t }        = useTranslation();
  const { token }    = useSessionStore();

  const videoId = searchParams.get('id');
  const [status,   setStatus]   = useState('pending');
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error,    setError]    = useState<string | null>(null);
  const [stepIdx,  setStepIdx]  = useState(0);

  useEffect(() => {
    if (!videoId) return;
    let stopped = false;

    async function poll() {
      try {
        const data = await getVideoStatus(Number(videoId), token ?? undefined);
        if (stopped) return;

        setStatus(data.status);

        if (data.status === 'complete' || data.status === 'completed') {
          setVideoUrl(data.video_url ?? null);
          return;
        }
        if (data.status === 'failed') {
          setError(data.error_message ?? t.errors.videoFailed);
          return;
        }

        setStepIdx(prev => (prev + 1) % STEPS.length);
        setTimeout(poll, 4000);
      } catch {
        if (!stopped) setError(t.errors.generic);
      }
    }

    poll();
    return () => { stopped = true; };
  }, [videoId]);

  const isLoading = status === 'pending' || status === 'queued';
  const isDone    = status === 'complete' || status === 'completed';
  const isFailed  = status === 'failed';

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex flex-col min-w-0 bg-[#0f0f0f]">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-white/10 shrink-0">
          <button onClick={() => router.push('/')} className="text-white/50 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </button>
          <h1 className="text-white font-semibold">
            {isDone ? t.video.ready : isFailed ? t.video.failed : t.video.generating}
          </h1>
        </div>

        <div className="flex-1 flex items-center justify-center px-4 py-12 overflow-y-auto">
          {/* No video ID */}
          {!videoId && (
            <p className="text-white/50">No video ID provided.</p>
          )}

          {/* ── Loading state ── */}
          {videoId && isLoading && (
            <div className="text-center max-w-sm w-full">
              <div className="w-20 h-20 mx-auto mb-8 relative">
                <div className="w-20 h-20 rounded-full border-4 border-white/10" />
                <div className="w-20 h-20 rounded-full border-4 border-purple-500 border-t-transparent absolute inset-0 animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-sm font-bold">
                    L
                  </div>
                </div>
              </div>

              <h2 className="text-white text-xl font-semibold mb-2">{t.video.generating}</h2>
              <p className="text-white/50 text-sm mb-8">{t.video.generatingDesc}</p>

              <div className="space-y-3 text-left">
                {STEPS.map((step, i) => {
                  const done   = i < stepIdx;
                  const active = i === stepIdx;
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${
                        done   ? 'bg-green-500' :
                        active ? 'bg-purple-500 animate-pulse' :
                                 'bg-white/10'
                      }`}>
                        {done   && <CheckCircle size={12} className="text-white" />}
                        {active && <Loader size={10} className="text-white animate-spin" />}
                      </div>
                      <span className={`text-sm transition-colors ${
                        done   ? 'text-white/50 line-through' :
                        active ? 'text-white' :
                                 'text-white/25'
                      }`}>
                        {step}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Done — show player ── */}
          {videoId && isDone && videoUrl && (
            <div className="w-full max-w-3xl">
              <div className="aspect-video rounded-2xl overflow-hidden bg-black shadow-2xl shadow-purple-500/10 mb-4">
                <video src={videoUrl} controls autoPlay className="w-full h-full" />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-white/50 text-sm">✅ {t.video.ready}</p>
                <a
                  href={videoUrl}
                  download
                  className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/15 rounded-xl text-white text-sm transition-colors"
                >
                  <Download size={14} />
                  {t.download}
                </a>
              </div>
            </div>
          )}

          {videoId && isDone && !videoUrl && (
            <div className="text-center">
              <CheckCircle size={48} className="text-green-400 mx-auto mb-4" />
              <p className="text-white font-semibold">Video ready — loading player…</p>
            </div>
          )}

          {/* ── Failed ── */}
          {videoId && isFailed && (
            <div className="text-center max-w-sm">
              <XCircle size={48} className="text-red-400 mx-auto mb-4" />
              <h2 className="text-white font-semibold mb-2">{t.video.failed}</h2>
              <p className="text-white/50 text-sm mb-6">{error ?? t.video.failedDesc}</p>
              <button
                onClick={() => router.push('/')}
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-colors"
              >
                {t.back}
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function VideosPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <VideosContent />
    </Suspense>
  );
}
