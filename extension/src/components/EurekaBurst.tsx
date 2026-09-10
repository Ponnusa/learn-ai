'use client';

import { useEffect, useRef } from 'react';

/**
 * A handful of quick claps synthesized with the Web Audio API — filtered
 * decaying noise bursts, the standard technique for a percussive
 * clap/snap sound — rather than bundling an audio file. Keeps this
 * self-contained (no asset to source/license) and consistent with the
 * confetti above it (hand-rolled, no new dependency). Best-effort: any
 * failure (Web Audio unavailable, autoplay blocked) is swallowed — the
 * visual celebration still plays either way.
 */
function playClapSound() {
  try {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioContextClass();
    const now = ctx.currentTime;
    const clapTimes = [0, 0.11, 0.2, 0.33]; // slightly irregular spacing reads more like real applause than a metronome

    clapTimes.forEach((delay, i) => {
      const duration = 0.09;
      const bufferSize = Math.floor(ctx.sampleRate * duration);
      const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let j = 0; j < bufferSize; j++) {
        data[j] = (Math.random() * 2 - 1) * Math.exp(-j / (bufferSize * 0.18)); // fast decay = percussive, not a tone
      }

      const noise = ctx.createBufferSource();
      noise.buffer = buffer;

      const bandpass = ctx.createBiquadFilter();
      bandpass.type = 'bandpass';
      bandpass.frequency.value = 1200 + (i % 2) * 600; // slight variation per clap so they don't sound identical
      bandpass.Q.value = 0.7;

      const gain = ctx.createGain();
      gain.gain.value = 0.22;

      noise.connect(bandpass).connect(gain).connect(ctx.destination);
      noise.start(now + delay);
    });

    setTimeout(() => ctx.close(), 900);
  } catch {
    // No Web Audio, or autoplay blocked — the confetti/mascot still show.
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
 * Full-screen confetti shower + mascot + synthesized claps, shown for ~4s
 * when a guided-discovery chain resolves. Hand-rolled canvas animation
 * rather than a new dependency (canvas-confetti etc.) — this codebase
 * doesn't pull in animation libraries, and a particle shower is simple
 * enough to not need one. Purely decorative: `aria-hidden`, respects
 * prefers-reduced-motion (gates the sound too, not just the visuals), and
 * never intercepts clicks.
 */
export function EurekaBurst({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    playClapSound();

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

      if (elapsed < EUREKA_BURST_DURATION) {
        rafId = requestAnimationFrame(frame);
      }
    }
    rafId = requestAnimationFrame(frame);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(rafId);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  }, [active]);

  if (!active) return null;

  return (
    <div className="fixed inset-0 z-[70] pointer-events-none overflow-hidden" aria-hidden="true">
      <canvas ref={canvasRef} className="w-full h-full" />
      <div className="absolute inset-0 flex items-center justify-center">
        <img src="/branding/genie-mascot-240.png" alt="" className="w-24 h-24 eureka-clap" />
      </div>
    </div>
  );
}
