'use client';
import { useState, useEffect, useLayoutEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { X, ArrowRight, Check } from 'lucide-react';

export interface TourStep {
  title: string;
  body: string;
  /** CSS selector for the element to spotlight. Omit for a centered modal step. */
  targetSelector?: string;
}

interface Rect { top: number; left: number; width: number; height: number; }

const PAD = 10;
const TOOLTIP_W = 300;

export function SpotlightTour({
  steps,
  storageKey,
  onDone,
}: {
  steps: TourStep[];
  storageKey: string;
  onDone: () => void;
}) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const current = steps[step];
  const isLast = step === steps.length - 1;

  const finish = useCallback(() => {
    try { localStorage.setItem(storageKey, '1'); } catch {}
    onDone();
  }, [storageKey, onDone]);

  // Position the spotlight over the target element
  useLayoutEffect(() => {
    if (!mounted || !current.targetSelector) { setRect(null); return; }
    const el = document.querySelector(current.targetSelector);
    if (!el) { setRect(null); return; }
    const r = el.getBoundingClientRect();
    setRect({ top: r.top - PAD, left: r.left - PAD, width: r.width + PAD * 2, height: r.height + PAD * 2 });
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [step, current.targetSelector, mounted]);

  // Keyboard: Esc to skip, → to advance
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') finish();
      if (e.key === 'ArrowRight' || e.key === 'Enter') advance();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  function advance() {
    if (isLast) finish();
    else setStep(s => s + 1);
  }

  if (!mounted) return null;

  // Tooltip position: below the spotlight if room, else above; fallback to centre
  let tooltipStyle: React.CSSProperties = {};
  if (rect) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const spBottom = rect.top + rect.height;
    const left = Math.max(12, Math.min(rect.left, vw - TOOLTIP_W - 12));
    if (spBottom + 180 < vh) {
      tooltipStyle = { top: spBottom + 14, left };
    } else {
      tooltipStyle = { bottom: vh - rect.top + 14, left };
    }
  } else {
    tooltipStyle = { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' };
  }

  return createPortal(
    // Transparent full-screen trap — click to skip
    <div className="fixed inset-0 z-[9999]" onClick={finish}>

      {/* Dark surround — four quadrant panels that leave the spotlight open */}
      {rect ? (
        <>
          <div className="absolute bg-black/65" style={{ inset: 0, clipPath: `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${rect.left}px ${rect.top}px, ${rect.left}px ${rect.top + rect.height}px, ${rect.left + rect.width}px ${rect.top + rect.height}px, ${rect.left + rect.width}px ${rect.top}px, ${rect.left}px ${rect.top}px)` }} />
          {/* Spotlight border ring */}
          <div className="absolute pointer-events-none rounded-xl"
            style={{ top: rect.top, left: rect.left, width: rect.width, height: rect.height, boxShadow: '0 0 0 2px rgba(139,92,246,0.7)', transition: 'all 0.25s ease' }}
          />
        </>
      ) : (
        <div className="absolute inset-0 bg-black/65" />
      )}

      {/* Tooltip */}
      <div
        className="absolute z-10 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl shadow-2xl p-5 flex flex-col gap-3 transition-all duration-250"
        style={{ width: TOOLTIP_W, ...tooltipStyle }}
        onClick={e => e.stopPropagation()}
      >
        {/* Step dots + close */}
        <div className="flex items-center gap-1.5">
          {steps.map((_, i) => (
            <div key={i} className={`h-1.5 rounded-full transition-all duration-300 ${
              i === step ? 'w-5 bg-purple-500' : i < step ? 'w-2 bg-purple-400/50' : 'w-2 bg-[var(--bd)]'
            }`} />
          ))}
          <button onClick={finish} className="ml-auto text-[var(--tx8)] hover:text-[var(--tx3)] transition-colors p-0.5">
            <X size={13} />
          </button>
        </div>

        <div>
          <p className="text-[var(--tx1)] font-semibold text-sm mb-1">{current.title}</p>
          <p className="text-[var(--tx5)] text-xs leading-relaxed whitespace-pre-line">{current.body}</p>
        </div>

        <div className="flex items-center justify-between pt-1">
          {step > 0 ? (
            <button onClick={() => setStep(s => s - 1)} className="text-[11px] text-[var(--tx7)] hover:text-[var(--tx3)] transition-colors">
              ← Back
            </button>
          ) : (
            <button onClick={finish} className="text-[11px] text-[var(--tx8)] hover:text-[var(--tx5)] transition-colors">
              Skip tour
            </button>
          )}
          <button
            onClick={advance}
            className="flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white transition-colors"
          >
            {isLast ? <><Check size={11} /> Got it!</> : <>Next <ArrowRight size={11} /></>}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
