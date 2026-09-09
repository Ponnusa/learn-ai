'use client';

import { useEffect, useRef } from 'react';

const COLORS = ['#f97316', '#eab308', '#22c55e', '#3b82f6', '#a855f7', '#ec4899'];
const DURATION = 1600; // ms — brief, per the "for a brief second" ask
const PARTICLE_COUNT = 140;

interface Particle {
  x: number; y: number;
  vx: number; vy: number;
  size: number;
  color: string;
  rotation: number;
  vr: number;
  shape: 'rect' | 'circle';
}

/**
 * Full-screen confetti burst + clap emoji, shown for ~1.6s when a
 * guided-discovery chain resolves. Hand-rolled canvas animation rather
 * than a new dependency (canvas-confetti etc.) — this codebase doesn't
 * pull in animation libraries, and a one-shot particle burst is simple
 * enough to not need one. Purely decorative: `aria-hidden`, respects
 * prefers-reduced-motion, and never intercepts clicks.
 */
export function EurekaBurst({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const particles: Particle[] = Array.from({ length: PARTICLE_COUNT }, () => {
      const fromLeft = Math.random() < 0.5;
      return {
        x: fromLeft ? -20 : canvas.width + 20,
        y: canvas.height * (0.15 + Math.random() * 0.5),
        vx: (fromLeft ? 1 : -1) * (6 + Math.random() * 10),
        vy: -9 - Math.random() * 7,
        size: 6 + Math.random() * 6,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        rotation: Math.random() * Math.PI * 2,
        vr: (Math.random() - 0.5) * 0.35,
        shape: Math.random() < 0.5 ? 'rect' : 'circle',
      };
    });

    const gravity = 0.35;
    const start = performance.now();
    let rafId: number;

    function frame(now: number) {
      const elapsed = now - start;
      ctx!.clearRect(0, 0, canvas!.width, canvas!.height);
      const alpha = Math.max(0, 1 - elapsed / DURATION);

      for (const p of particles) {
        p.vy += gravity;
        p.x += p.vx;
        p.y += p.vy;
        p.rotation += p.vr;

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

      if (elapsed < DURATION) {
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
        <span className="text-7xl eureka-clap">👏</span>
      </div>
    </div>
  );
}
