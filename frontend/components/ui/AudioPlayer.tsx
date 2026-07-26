'use client';
import { useRef, useEffect, useState } from 'react';

const SPEEDS = [0.75, 1, 1.25, 1.5] as const;
type Speed = (typeof SPEEDS)[number];
const STORAGE_KEY = 'learnai-audio-speed';

export function getSavedAudioSpeed(): Speed {
  if (typeof localStorage === 'undefined') return 1;
  const v = parseFloat(localStorage.getItem(STORAGE_KEY) ?? '1');
  return (SPEEDS.includes(v as Speed) ? v : 1) as Speed;
}

export function AudioPlayer({ src, className }: { src: string; className?: string }) {
  const ref = useRef<HTMLAudioElement>(null);
  const [speed, setSpeed] = useState<Speed>(() => getSavedAudioSpeed());

  function applySpeed(s: Speed) {
    if (ref.current) ref.current.playbackRate = s;
  }

  useEffect(() => { applySpeed(speed); }, [speed]);

  function pick(s: Speed) {
    setSpeed(s);
    localStorage.setItem(STORAGE_KEY, String(s));
    applySpeed(s);
  }

  return (
    <div className={className}>
      <audio ref={ref} controls src={src} onLoadedMetadata={() => applySpeed(speed)} className="w-full" />
      <div className="flex items-center gap-1 mt-1.5">
        <span className="text-[10px] text-[var(--tx8)] mr-0.5">Speed</span>
        {SPEEDS.map(s => (
          <button key={s} onClick={() => pick(s)}
            className={`text-[10px] leading-none px-1.5 py-0.5 rounded transition-colors ${
              speed === s
                ? 'bg-purple-500/20 text-purple-400 font-semibold'
                : 'text-[var(--tx8)] hover:text-[var(--tx2)]'
            }`}>
            {s}×
          </button>
        ))}
      </div>
    </div>
  );
}
