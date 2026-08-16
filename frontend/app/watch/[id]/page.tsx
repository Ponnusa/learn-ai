'use client';
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Loader2, BookOpen, AlertTriangle, ArrowLeft } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface VideoData {
  id: number;
  status: string;
  video_url: string;
  prompt: string;
  subject: string | null;
  duration_secs: number | null;
}

export default function WatchPage() {
  const { id } = useParams<{ id: string }>();
  const [video, setVideo]   = useState<VideoData | null>(null);
  const [error, setError]   = useState('');
  const [loading, setLoading] = useState(true);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/videos/${id}/watch`)
      .then(r => {
        if (!r.ok) throw new Error('Video not found');
        return r.json();
      })
      .then(setVideo)
      .catch(() => setError('This video could not be found or is no longer available.'))
      .finally(() => setLoading(false));
  }, [id]);

  function blockContext(e: React.MouseEvent) {
    e.preventDefault();
  }

  if (loading) return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center gap-4 px-4">
      <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center">
        <AlertTriangle size={24} className="text-red-400" />
      </div>
      <p className="text-[var(--tx3)] text-sm text-center max-w-xs">{error}</p>
      <a href="https://www.learnx-ai.com"
        className="flex items-center gap-1.5 text-sm text-purple-400 hover:text-purple-300 transition-colors">
        <ArrowLeft size={14} /> Go to LearnX AI
      </a>
    </div>
  );

  if (!video) return null;

  const title = video.prompt
    ? video.prompt.length > 80 ? video.prompt.slice(0, 77) + '…' : video.prompt
    : 'Video';

  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col">
      {/* Minimal header */}
      <header className="border-b border-[var(--bd)] px-5 py-3 flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-600 flex items-center justify-center">
            <BookOpen size={14} className="text-white" />
          </div>
          <span className="text-[var(--tx1)] text-sm font-semibold">LearnX AI</span>
        </div>
        {video.subject && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--ov1)] text-[var(--tx6)]">
            {video.subject}
          </span>
        )}
      </header>

      {/* Player area */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-8 gap-6">
        <div className="w-full max-w-3xl">
          {/* Title */}
          <p className="text-[var(--tx1)] text-sm font-medium mb-4 line-clamp-2">{title}</p>

          {/* Video — locked down player */}
          <div className="rounded-2xl overflow-hidden bg-black shadow-2xl">
            <video
              ref={videoRef}
              src={video.video_url}
              controls
              controlsList="nodownload nofullscreen"
              disablePictureInPicture
              onContextMenu={blockContext}
              className="w-full aspect-video"
              preload="metadata"
            />
          </div>

          {/* Footer note */}
          <p className="text-[var(--tx7)] text-xs mt-4 text-center">
            This video is part of a course on{' '}
            <a href="https://www.learnx-ai.com" className="text-purple-400 hover:underline">
              LearnX AI
            </a>
            . Sign in to access the full course.
          </p>
        </div>
      </main>
    </div>
  );
}
