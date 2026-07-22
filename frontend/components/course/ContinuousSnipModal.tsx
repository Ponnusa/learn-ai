'use client';
/**
 * ContinuousSnipModal — renders all PDF pages in a vertical scroll (like the
 * native iframe viewer) so the teacher can read context freely, then drag to
 * clip any visible region and send it to Studio chat.
 */
import { useState, useRef, useEffect } from 'react';
import { X, Loader2, Scissors } from 'lucide-react';

const PDFJS_URL  = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const RENDER_SCALE = 1.4;

declare global { interface Window { pdfjsLib: any } }

interface Rect { x: number; y: number; w: number; h: number }

export interface SnipAction {
  label:   string;
  primary?: boolean;
  icon:    React.ComponentType<{ size?: number; className?: string }>;
  onClick: (imageDataUrl: string) => void;
}

interface Props {
  file:    File;
  onClose: () => void;
  actions: SnipAction[];
}

export function ContinuousSnipModal({ file, onClose, actions }: Props) {
  const [pdfDoc,    setPdfDoc]    = useState<any>(null);
  const [numPages,  setNumPages]  = useState(0);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [loadError, setLoadError] = useState('');

  // Selection state
  const [drawing,       setDrawing]       = useState(false);
  const [activeIdx,     setActiveIdx]     = useState<number | null>(null);
  const [startPos,      setStartPos]      = useState<{ x: number; y: number } | null>(null);
  const [selRect,       setSelRect]       = useState<Rect | null>(null);
  const [capturedUrl,   setCapturedUrl]   = useState<string | null>(null);
  const [menuPos,       setMenuPos]       = useState<{ x: number; y: number } | null>(null);

  const canvasRefs = useRef<(HTMLCanvasElement | null)[]>([]);

  // ── Load PDF.js + document ──────────────────────────────────────────────────
  useEffect(() => {
    async function init() {
      try {
        if (!window.pdfjsLib) {
          await new Promise<void>((resolve, reject) => {
            const s = document.createElement('script');
            s.src = PDFJS_URL;
            s.onload  = () => resolve();
            s.onerror = () => reject(new Error('Failed to load PDF.js'));
            document.head.appendChild(s);
          });
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_URL;
        }
        const doc = await window.pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setLoadState('ready');
      } catch (e: any) {
        setLoadError(e.message || 'Failed to load PDF');
        setLoadState('error');
      }
    }
    init();
  }, [file]);

  // ── Render all pages once PDF is ready ─────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc || loadState !== 'ready') return;
    let cancelled = false;
    (async () => {
      for (let i = 0; i < numPages; i++) {
        const canvas = canvasRefs.current[i];
        if (!canvas || cancelled) break;
        try {
          const page  = await pdfDoc.getPage(i + 1);
          const dpr   = window.devicePixelRatio || 1;
          const base  = page.getViewport({ scale: RENDER_SCALE });
          const hi    = page.getViewport({ scale: RENDER_SCALE * dpr });
          canvas.width  = hi.width;
          canvas.height = hi.height;
          canvas.style.width  = `${base.width}px`;
          canvas.style.height = `${base.height}px`;
          await page.render({ canvasContext: canvas.getContext('2d')!, viewport: hi }).promise;
        } catch { /* ignore */ }
      }
    })();
    return () => { cancelled = true; };
  }, [pdfDoc, numPages, loadState]);

  // ── Selection helpers ───────────────────────────────────────────────────────
  function clearSel() {
    setSelRect(null); setCapturedUrl(null); setMenuPos(null);
    setActiveIdx(null); setStartPos(null); setDrawing(false);
  }

  function capture(pageIdx: number, rect: Rect) {
    const canvas = canvasRefs.current[pageIdx];
    if (!canvas) return;
    const sx = canvas.width  / canvas.offsetWidth;
    const sy = canvas.height / canvas.offsetHeight;
    const off = document.createElement('canvas');
    off.width  = Math.round(rect.w * sx);
    off.height = Math.round(rect.h * sy);
    off.getContext('2d')!.drawImage(
      canvas,
      Math.round(rect.x * sx), Math.round(rect.y * sy), off.width, off.height,
      0, 0, off.width, off.height,
    );
    setCapturedUrl(off.toDataURL('image/png'));
    const cb = canvas.getBoundingClientRect();
    setMenuPos({ x: cb.left + rect.x + rect.w / 2, y: cb.top + rect.y + rect.h + 12 });
  }

  // ── Mouse handlers per page overlay ────────────────────────────────────────
  function handleDown(idx: number, e: React.MouseEvent<HTMLDivElement>) {
    e.stopPropagation();
    if (capturedUrl) { clearSel(); return; }
    const r = e.currentTarget.getBoundingClientRect();
    setActiveIdx(idx);
    setStartPos({ x: e.clientX - r.left, y: e.clientY - r.top });
    setDrawing(true);
    setSelRect(null);
    setCapturedUrl(null);
  }

  function handleMove(idx: number, e: React.MouseEvent<HTMLDivElement>) {
    if (!drawing || activeIdx !== idx || !startPos) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    setSelRect({
      x: Math.min(startPos.x, x), y: Math.min(startPos.y, y),
      w: Math.abs(x - startPos.x), h: Math.abs(y - startPos.y),
    });
  }

  function handleUp(idx: number, e: React.MouseEvent<HTMLDivElement>) {
    e.stopPropagation();
    if (!drawing || activeIdx !== idx) return;
    setDrawing(false);
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const rect: Rect = selRect ?? {
      x: Math.min(startPos!.x, x), y: Math.min(startPos!.y, y),
      w: Math.abs(x - startPos!.x), h: Math.abs(y - startPos!.y),
    };
    if (rect.w < 10 || rect.h < 10) { clearSel(); return; }
    capture(idx, rect);
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  const menuItemCount = actions.length;
  const menuH = menuItemCount * 44 + 32;

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'rgba(0,0,0,0.88)' }}>
      <style>{`
        @keyframes snipCtxIn { from{opacity:0;transform:scale(0.93)} to{opacity:1;transform:scale(1)} }
      `}</style>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-white/10 bg-[#111] shrink-0">
        <Scissors size={13} className="text-violet-400 shrink-0" />
        <span className="text-white/65 text-xs font-medium">Drag to clip any region</span>
        <span className="text-white/25 text-[11px]">· scroll to read · click background to clear</span>
        <button onClick={onClose}
          className="ml-auto w-7 h-7 flex items-center justify-center rounded-lg
                     text-white/35 hover:text-white/75 hover:bg-white/8 transition-colors shrink-0">
          <X size={15} />
        </button>
      </div>

      {/* ── Scrollable continuous pages ──────────────────────────────────── */}
      <div
        className="flex-1 overflow-y-auto bg-[#1c1c1c] py-5"
        onClick={() => capturedUrl && clearSel()}
      >
        {loadState === 'loading' && (
          <div className="flex items-center justify-center h-48 gap-2 text-white/35 text-sm">
            <Loader2 size={15} className="animate-spin" /> Loading…
          </div>
        )}
        {loadState === 'error' && (
          <div className="flex items-center justify-center h-48 text-red-400 text-sm">{loadError}</div>
        )}
        {loadState === 'ready' && (
          <div className="flex flex-col items-center gap-4">
            {Array.from({ length: numPages }, (_, i) => (
              <div key={i} className="relative inline-block select-none"
                style={{ boxShadow: '0 2px 16px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04)' }}>

                <canvas
                  ref={el => { canvasRefs.current[i] = el; }}
                  style={{ display: 'block' }}
                />

                {/* Per-page drag overlay */}
                <div
                  className="absolute inset-0"
                  style={{ cursor: capturedUrl ? 'default' : 'crosshair', touchAction: 'none' }}
                  onMouseDown={e => handleDown(i, e)}
                  onMouseMove={e => handleMove(i, e)}
                  onMouseUp={e => handleUp(i, e)}
                  onMouseLeave={() => drawing && activeIdx === i && setDrawing(false)}
                >
                  {/* Live selection */}
                  {selRect && activeIdx === i && !capturedUrl && (
                    <div className="absolute border-2 border-violet-400 bg-violet-500/10 rounded-sm pointer-events-none"
                      style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h }} />
                  )}
                  {/* Captured selection highlight */}
                  {capturedUrl && selRect && activeIdx === i && (
                    <>
                      <div className="absolute inset-0 bg-black/40 pointer-events-none" />
                      <div className="absolute border-2 border-violet-400 rounded-sm pointer-events-none"
                        style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h,
                                 outline: '9999px solid rgba(0,0,0,0.40)' }} />
                    </>
                  )}
                </div>

                {/* Page number badge */}
                <div className="absolute bottom-1.5 right-2 text-[10px] text-white/20 pointer-events-none select-none">
                  {i + 1} / {numPages}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Context menu (fixed to viewport) ─────────────────────────────── */}
      {capturedUrl && menuPos && (() => {
        const W  = 216;
        const vw = window.innerWidth, vh = window.innerHeight;
        const cx = Math.max(8, Math.min(vw - W - 8, menuPos.x - W / 2));
        const cy = menuPos.y + menuH < vh ? menuPos.y : menuPos.y - menuH - (selRect?.h ?? 0) - 24;
        return (
          <div
            className="fixed z-[60] bg-[#1c1c1e] border border-white/[0.13] rounded-2xl shadow-2xl overflow-hidden"
            style={{ left: cx, top: Math.max(8, Math.min(vh - menuH - 8, cy)), width: W,
                     animation: 'snipCtxIn 0.13s ease' }}
            onMouseDown={e => e.stopPropagation()}
            onClick={e => e.stopPropagation()}
          >
            {actions.map((a, i) => {
              const Icon = a.icon;
              return (
                <button key={i} onClick={() => a.onClick(capturedUrl!)}
                  className={a.primary
                    ? 'w-full flex items-center gap-2.5 px-4 py-3 text-sm font-semibold text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 transition-colors'
                    : 'w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium text-white/60 hover:text-white hover:bg-white/[0.07] transition-colors'
                  }>
                  <Icon size={a.primary ? 14 : 13} className="shrink-0" /> {a.label}
                </button>
              );
            })}
            <div className="h-px bg-white/[0.07]" />
            <button onClick={clearSel}
              className="w-full flex items-center gap-2 px-4 py-1.5 text-[10px] text-white/25 hover:text-white/50 hover:bg-white/[0.04] transition-colors">
              <X size={10} className="shrink-0" /> Clear selection
            </button>
          </div>
        );
      })()}
    </div>
  );
}
