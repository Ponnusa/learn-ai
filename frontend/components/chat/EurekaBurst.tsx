'use client';

import { useEffect, useRef } from 'react';

// Real applause clip (public/audio/eureka-applause.mp3) — a synthesized
// noise-burst "clap" was tried first but didn't sound convincing, so this
// is a licensed recording instead. The source file runs much longer than
// the ~4s confetti burst, so playback is faded out and stopped in sync
// with EUREKA_BURST_DURATION from the same rAF loop driving the confetti,
// rather than letting it run past the visual celebration.
const APPLAUSE_SRC = '/audio/eureka-applause.mp3';
const APPLAUSE_VOLUME = 0.5;
const APPLAUSE_FADE_MS = 500; // fade-out window before EUREKA_BURST_DURATION

function startApplause(): HTMLAudioElement | null {
  try {
    const audio = new Audio(APPLAUSE_SRC);
    audio.volume = APPLAUSE_VOLUME;
    audio.play().catch(() => {
      // Autoplay blocked — the confetti/mascot still show.
    });
    return audio;
  } catch {
    return null; // Audio unavailable — the confetti/mascot still show.
  }
}

const COLORS = ['#f97316', '#eab308', '#22c55e', '#3b82f6', '#a855f7', '#ec4899'];
export const EUREKA_BURST_DURATION = 4200; // ms — exported so page.tsx can time the unmount to match
const SPAWN_WINDOW = 1400; // ms — particles launch on a staggered window, not all at once,
                            // so it reads as a sustained shower rather than one flat pop
const PARTICLE_COUNT = 260;

interface Particle {
  born: number;    // ms after mount when this particle launches
  lifespan: number;
  x: number; y: number;
  vx: number; vy: number;
  size: number;
  color: string;
  rotation: number;
  vr: number;
  phase: number;    // flutter wobble offset
  shape: 'rect' | 'circle';
}

/**
 * Full-screen confetti shower + mascot + applause, shown for ~4s when a
 * guided-discovery chain resolves. The confetti is hand-rolled canvas
 * animation rather than a new dependency (canvas-confetti etc.) — this
 * codebase doesn't pull in animation libraries, and a particle shower is
 * simple enough to not need one. Purely decorative: `aria-hidden`, respects
 * prefers-reduced-motion (gates the applause too, not just the visuals),
 * and never intercepts clicks.
 */
export function EurekaBurst({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const applause = startApplause();

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const particles: Particle[] = Array.from({ length: PARTICLE_COUNT }, () => {
      const fromLeft = Math.random() < 0.5;
      return {
        born: Math.random() * SPAWN_WINDOW,
        lifespan: 2400 + Math.random() * 900,
        x: fromLeft ? -20 : canvas.width + 20,
        y: canvas.height * (0.1 + Math.random() * 0.55),
        vx: (fromLeft ? 1 : -1) * (5 + Math.random() * 9),
        vy: -8 - Math.random() * 6,
        size: 6 + Math.random() * 6,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        rotation: Math.random() * Math.PI * 2,
        vr: (Math.random() - 0.5) * 0.3,
        phase: Math.random() * Math.PI * 2,
        shape: Math.random() < 0.5 ? 'rect' : 'circle',
      };
    });

    const gravity = 0.32;
    const terminalVy = 3.2; // gentle drifting fall once air resistance catches up, not a straight plummet
    const drag = 0.985;
    const start = performance.now();
    let rafId: number;

    function frame(now: number) {
      const elapsed = now - start;
      ctx!.clearRect(0, 0, canvas!.width, canvas!.height);

      for (const p of particles) {
        const age = elapsed - p.born;
        if (age < 0) continue; // hasn't launched yet

        p.vy = Math.min(p.vy + gravity, terminalVy);
        p.vx *= drag;
        p.x += p.vx + Math.sin(age / 260 + p.phase) * 1.4; // flutter
        p.y += p.vy;
        p.rotation += p.vr;

        const fadeStart = p.lifespan - 700;
        const alpha = age < fadeStart ? 1 : Math.max(0, 1 - (age - fadeStart) / 700);
        if (alpha <= 0) continue;

        ctx!.save();
        ctx!.translate(p.x, p.y);
        ctx!.rotate(p.rotation);
        ctx!.globalAlpha = alpha;
        ctx!.fillStyle = p.color;
        if (p.shape === 'rect') {
          ctx!.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
        } else {
          ctx!.beginPath();
          ctx!.arc(0, 0, p.size / 2, 0, Math.PI * 2);
          ctx!.fill();
        }
        ctx!.restore();
      }

      if (applause) {
        const fadeStart = EUREKA_BURST_DURATION - APPLAUSE_FADE_MS;
        applause.volume =
          elapsed < fadeStart
            ? APPLAUSE_VOLUME
            : Math.max(0, APPLAUSE_VOLUME * (1 - (elapsed - fadeStart) / APPLAUSE_FADE_MS));
      }

      if (elapsed < EUREKA_BURST_DURATION) {
        rafId = requestAnimationFrame(frame);
      }
    }
    rafId = requestAnimationFrame(frame);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(rafId);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (applause) {
        applause.pause();
        applause.currentTime = 0;
      }
    };
  }, [active]);

  if (!active) return null;

  return (
    <div className="fixed inset-0 z-[70] pointer-events-none overflow-hidden" aria-hidden="true">
      <canvas ref={canvasRef} className="w-full h-full" />
      <div className="absolute inset-0 flex items-center justify-center">
        <img src="/branding/genie-mascot.png" alt="" className="w-28 h-28 eureka-clap" />
      </div>
    </div>
  );
}
