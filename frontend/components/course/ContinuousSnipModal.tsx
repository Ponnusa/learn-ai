'use client';
/**
 * ContinuousSnipModal — renders all PDF pages in a vertical scroll so the
 * teacher can read freely, then drag to clip any region for Studio chat.
 *
 * Drag state lives in refs (not React state) so event handlers always read
 * fresh values and don't suffer stale-closure bugs. A global window mouseup
 * listener ensures capture fires even when the cursor leaves the overlay.
 */
import { useState, useRef, useEffect, useCallback } from 'react';
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
  // ── PDF load state ──────────────────────────────────────────────────────────
  const [pdfDoc,    setPdfDoc]    = useState<any>(null);
  const [numPages,  setNumPages]  = useState(0);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [loadError, setLoadError] = useState('');

  // ── Rendered selection (UI only — real drag values live in refs) ────────────
  const [selRect,     setSelRect]     = useState<Rect | null>(null);
  const [selPageIdx,  setSelPageIdx]  = useState<number | null>(null);
  const [capturedUrl, setCapturedUrl] = useState<string | null>(null);
  const [menuPos,     setMenuPos]     = useState<{ x: number; y: number } | null>(null);
  const [isDragging,  setIsDragging]  = useState(false);

  // ── Refs: mutable drag state read reliably inside window callbacks ──────────
  const draggingRef  = useRef(false);
  const pageIdxRef   = useRef<number | null>(null);
  const startRef     = useRef<{ x: number; y: number } | null>(null);
  const overlayRects = useRef<(DOMRect | null)[]>([]);   // overlay bounding boxes per page
  const canvasRefs   = useRef<(HTMLCanvasElement | null)[]>([]);
  const overlayRefs  = useRef<(HTMLDivElement | null)[]>([]);

  // ── Load PDF.js + open document ─────────────────────────────────────────────
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

  // ── Render all pages sequentially once doc is loaded ───────────────────────
  useEffect(() => {
    if (!pdfDoc || loadState !== 'ready') return;
    let cancelled = false;
    (async () => {
      for (let i = 0; i < numPages; i++) {
        const canvas = canvasRefs.current[i];
        if (!canvas || cancelled) break;
        try {
          const page = await pdfDoc.getPage(i + 1);
          const dpr  = window.devicePixelRatio || 1;
          const base = page.getViewport({ scale: RENDER_SCALE });
          const hi   = page.getViewport({ scale: RENDER_SCALE * dpr });
          canvas.width  = hi.width;
          canvas.height = hi.height;
          canvas.style.width  = `${base.width}px`;
          canvas.style.height = `${base.height}px`;
          await page.render({ canvasContext: canvas.getContext('2d')!, viewport: hi }).promise;
        } catch { /* ignore cancelled renders */ }
      }
    })();
    return () => { cancelled = true; };
  }, [pdfDoc, numPages, loadState]);

  // ── Helpers ─────────────────────────────────────────────────────────────────
  function clearSel() {
    setSelRect(null);
    setSelPageIdx(null);
    setCapturedUrl(null);
    setMenuPos(null);
  }

  function doCapture(pageIdx: number, rect: Rect) {
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

  // ── Global mouseup — fires reliably even when cursor left the overlay ───────
  const handleGlobalMouseUp = useCallback((e: MouseEvent) => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    setIsDragging(false);

    const idx   = pageIdxRef.current;
    const start = startRef.current;
    if (idx === null || !start) { clearSel(); return; }

    // Compute rect relative to the overlay div for this page
    const overlayEl = overlayRefs.current[idx];
    if (!overlayEl) { clearSel(); return; }
    const r  = overlayEl.getBoundingClientRect();
    const ex = e.clientX - r.left;
    const ey = e.clientY - r.top;
    const rect: Rect = {
      x: Math.min(start.x, ex), y: Math.min(start.y, ey),
      w: Math.abs(ex - start.x), h: Math.abs(ey - start.y),
    };
    if (rect.w < 10 || rect.h < 10) { clearSel(); return; }
    setSelPageIdx(idx);
    setSelRect(rect);
    doCapture(idx, rect);
  }, []);  // stable — only reads refs and calls state setters

  useEffect(() => {
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, [handleGlobalMouseUp]);

  // ── Per-page mouse handlers ─────────────────────────────────────────────────
  function handleDown(idx: number, e: React.MouseEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (capturedUrl) { clearSel(); return; }
    const r = e.currentTarget.getBoundingClientRect();
    overlayRects.current[idx] = r;
    const pos = { x: e.clientX - r.left, y: e.clientY - r.top };
    draggingRef.current = true;
    pageIdxRef.current  = idx;
    startRef.current    = pos;
    setIsDragging(true);
    setSelRect(null);
    setSelPageIdx(idx);
    setCapturedUrl(null);
  }

  function handleMove(idx: number, e: React.MouseEvent<HTMLDivElement>) {
    if (!draggingRef.current || pageIdxRef.current !== idx) return;
    const r     = e.currentTarget.getBoundingClientRect();
    const start = startRef.current!;
    const x     = e.clientX - r.left;
    const y     = e.clientY - r.top;
    setSelRect({
      x: Math.min(start.x, x), y: Math.min(start.y, y),
      w: Math.abs(x - start.x), h: Math.abs(y - start.y),
    });
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  const menuH = actions.length * 44 + 32;

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'rgba(0,0,0,0.88)' }}>
      <style>{`
        @keyframes snipCtxIn { from { opacity:0; transform:scale(0.93) } to { opacity:1; transform:scale(1) } }
      `}</style>

      {/* Header */}
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

      {/* Scrollable pages */}
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

                {/* Drag overlay — no onMouseLeave, global mouseup handles release */}
                <div
                  ref={el => { overlayRefs.current[i] = el; }}
                  className="absolute inset-0"
                  style={{ cursor: capturedUrl ? 'default' : 'crosshair', touchAction: 'none', userSelect: 'none' }}
                  onMouseDown={e => handleDown(i, e)}
                  onMouseMove={e => handleMove(i, e)}
                >
                  {/* Live selection rect */}
                  {isDragging && selRect && selPageIdx === i && !capturedUrl && (
                    <div
                      className="absolute border-2 border-violet-400 bg-violet-500/10 rounded-sm pointer-events-none"
                      style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h }}
                    />
                  )}
                  {/* Captured highlight */}
                  {capturedUrl && selRect && selPageIdx === i && (
                    <>
                      <div className="absolute inset-0 bg-black/40 pointer-events-none" />
                      <div
                        className="absolute border-2 border-violet-400 rounded-sm pointer-events-none"
                        style={{
                          left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h,
                          outline: '9999px solid rgba(0,0,0,0.40)',
                        }}
                      />
                    </>
                  )}
                </div>

                <div className="absolute bottom-1.5 right-2 text-[10px] text-white/20 pointer-events-none select-none">
                  {i + 1} / {numPages}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Context menu */}
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
            {actions.map((a, idx) => {
              const Icon = a.icon;
              return (
                <button key={idx} onClick={() => a.onClick(capturedUrl!)}
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
