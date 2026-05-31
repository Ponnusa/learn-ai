'use client';
/**
 * PDFViewerModal — region-capture only.
 * Drag to select any area (text, diagram, equation, image).
 * The crop is uploaded to R2; the AI receives it as a vision message.
 *
 * DPR-aware canvas rendering (crisp on HiDPI/Retina).
 * Fit-to-width computed via rAF after first paint.
 */
import { useState, useRef, useEffect } from 'react';
import {
  X, ZoomIn, ZoomOut, ChevronLeft, ChevronRight,
  Send, Loader2, Lightbulb, AlignLeft, ListChecks,
  MessageSquare, Sparkles, Maximize2,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const PDFJS_URL  = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

const PAGE_LIMITS: Record<string, number> = {
  anonymous: 2, free: 3, learner: 10, pro: Infinity,
};
const ZOOM_STEP = 0.2;
const ZOOM_MIN  = 0.3;
const ZOOM_MAX  = 4.0;

interface Rect { x: number; y: number; w: number; h: number }
declare global { interface Window { pdfjsLib: any } }

interface PDFViewerModalProps {
  file: File;
  onClose: () => void;
  onAsk: (question: string, context: { imageDataUrl?: string }) => void;
}

export function PDFViewerModal({ file, onClose, onAsk }: PDFViewerModalProps) {
  const { user } = useSessionStore();
  const tier      = user?.tier ?? 'anonymous';
  const pageLimit = PAGE_LIMITS[tier] ?? 2;

  const canvasRef       = useRef<HTMLCanvasElement>(null);
  const scrollRef       = useRef<HTMLDivElement>(null);
  const overlayRef      = useRef<HTMLDivElement>(null);
  const inputRef        = useRef<HTMLInputElement>(null);

  const [pdfDoc,      setPdfDoc]      = useState<any>(null);
  const [numPages,    setNumPages]    = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale,       setScale]       = useState(1.0);
  const [fitScale,    setFitScale]    = useState(1.0);
  const [regionUrl,   setRegionUrl]   = useState<string | null>(null);
  const [customQ,     setCustomQ]     = useState('');
  const [showCustom,  setShowCustom]  = useState(false);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState('');
  const [showHint,    setShowHint]    = useState(true);

  // Region drawing
  const [drawing,  setDrawing]  = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [selRect,  setSelRect]  = useState<Rect | null>(null);

  // Refs for non-passive touch handlers
  const drawingRef  = useRef(false);
  const startPosRef = useRef<{ x: number; y: number } | null>(null);
  const selRectRef  = useRef<Rect | null>(null);
  drawingRef.current  = drawing;
  startPosRef.current = startPos;
  selRectRef.current  = selRect;

  const effectiveMax = numPages > 0 ? Math.min(numPages, pageLimit) : 0;

  // ── Load PDF.js + document ───────────────────────────────────────────────────
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
        const data = await file.arrayBuffer();
        const doc  = await window.pdfjsLib.getDocument({ data }).promise;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
      } catch (e: any) {
        setError(e.message || 'Failed to load PDF');
        setLoading(false);
      }
    }
    init();
  }, [file]);

  // ── Fit scale — rAF so clientWidth is real ───────────────────────────────────
  useEffect(() => {
    if (!pdfDoc) return;
    const raf = requestAnimationFrame(async () => {
      try {
        const page      = await pdfDoc.getPage(1);
        const naturalVp = page.getViewport({ scale: 1 });
        const availW    = (scrollRef.current?.clientWidth ?? 640) - 16;
        const fit       = parseFloat(Math.min(availW / naturalVp.width, ZOOM_MAX).toFixed(2));
        setFitScale(fit);
        setScale(fit);
      } catch { /* use default */ }
      setLoading(false);
      // Fade-away hint: show for 2.5 s after PDF is ready
      setTimeout(() => setShowHint(false), 2500);
    });
    return () => cancelAnimationFrame(raf);
  }, [pdfDoc]);

  // ── DPR-aware render ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;
    let cancelled = false;
    let renderTask: any = null;

    async function render() {
      try {
        const page    = await pdfDoc.getPage(currentPage);
        if (cancelled) return;
        const dpr     = window.devicePixelRatio || 1;
        const baseVp  = page.getViewport({ scale });
        const hiDpiVp = page.getViewport({ scale: scale * dpr });
        const canvas  = canvasRef.current!;
        canvas.width  = hiDpiVp.width;
        canvas.height = hiDpiVp.height;
        canvas.style.width  = `${baseVp.width}px`;
        canvas.style.height = `${baseVp.height}px`;
        renderTask = page.render({ canvasContext: canvas.getContext('2d')!, viewport: hiDpiVp });
        await renderTask.promise;
      } catch { /* cancelled */ }
    }

    clearRegion();
    render();
    return () => { cancelled = true; renderTask?.cancel?.(); };
  }, [pdfDoc, currentPage, scale]);

  // ── Non-passive touch listeners (prevent scroll during draw) ─────────────────
  useEffect(() => {
    const el = overlayRef.current;
    if (!el) return;

    function touchStart(e: TouchEvent) {
      e.preventDefault();
      const touch = e.touches[0];
      const r = el!.getBoundingClientRect();
      const pos = { x: touch.clientX - r.left, y: touch.clientY - r.top };
      startPosRef.current = pos;
      setStartPos(pos);
      setDrawing(true); drawingRef.current = true;
      setSelRect(null);  selRectRef.current = null;
      setRegionUrl(null);
    }
    function touchMove(e: TouchEvent) {
      e.preventDefault();
      if (!drawingRef.current || !startPosRef.current) return;
      const touch = e.touches[0];
      const r = el!.getBoundingClientRect();
      const x = touch.clientX - r.left, y = touch.clientY - r.top;
      const rect = {
        x: Math.min(startPosRef.current.x, x), y: Math.min(startPosRef.current.y, y),
        w: Math.abs(x - startPosRef.current.x), h: Math.abs(y - startPosRef.current.y),
      };
      selRectRef.current = rect;
      setSelRect(rect);
    }
    function touchEnd(e: TouchEvent) {
      e.preventDefault();
      if (!drawingRef.current) return;
      setDrawing(false); drawingRef.current = false;
      const r = selRectRef.current;
      if (r && r.w > 10 && r.h > 10) extractRegion(r);
    }

    el.addEventListener('touchstart', touchStart, { passive: false });
    el.addEventListener('touchmove',  touchMove,  { passive: false });
    el.addEventListener('touchend',   touchEnd,   { passive: false });
    return () => {
      el.removeEventListener('touchstart', touchStart);
      el.removeEventListener('touchmove',  touchMove);
      el.removeEventListener('touchend',   touchEnd);
    };
  }, []);

  // ── Ctrl/Cmd + wheel zoom ────────────────────────────────────────────────────
  useEffect(() => {
    const el = scrollRef.current; if (!el) return;
    function onWheel(e: WheelEvent) {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setScale(s => parseFloat(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP))).toFixed(2)));
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  // ── Mouse region drawing ─────────────────────────────────────────────────────
  function onMouseDown(e: React.MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    setStartPos({ x: e.clientX - r.left, y: e.clientY - r.top });
    setDrawing(true); setSelRect(null); setRegionUrl(null);
  }
  function onMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!drawing || !startPos) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    setSelRect({ x: Math.min(startPos.x, x), y: Math.min(startPos.y, y), w: Math.abs(x - startPos.x), h: Math.abs(y - startPos.y) });
  }
  function onMouseUp() {
    if (!drawing) return;
    setDrawing(false);
    if (selRect && selRect.w > 10 && selRect.h > 10) extractRegion(selRect);
  }

  function extractRegion(rect: Rect) {
    const canvas = canvasRef.current; if (!canvas) return;
    const sx = canvas.width / canvas.offsetWidth;
    const sy = canvas.height / canvas.offsetHeight;
    const off = document.createElement('canvas');
    off.width  = Math.round(rect.w * sx);
    off.height = Math.round(rect.h * sy);
    off.getContext('2d')!.drawImage(
      canvas,
      Math.round(rect.x * sx), Math.round(rect.y * sy), off.width, off.height,
      0, 0, off.width, off.height,
    );
    setRegionUrl(off.toDataURL('image/png'));
  }

  function clearRegion() {
    setSelRect(null); setRegionUrl(null);
    setCustomQ(''); setShowCustom(false);
  }

  function fire(prompt: string) {
    onAsk(prompt, { imageDataUrl: regionUrl ?? undefined });
  }
  function handleCustomSend() { const q = customQ.trim(); if (!q) return; fire(q); }
  function zoom(dir: 1 | -1) {
    setScale(s => parseFloat(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s + dir * ZOOM_STEP)).toFixed(2)));
  }

  // ────────────────────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm sm:p-3">
      <style>{`
        @keyframes fadeOut {
          0%   { opacity: 1; transform: translateX(-50%) translateY(0); }
          70%  { opacity: 1; transform: translateX(-50%) translateY(0); }
          100% { opacity: 0; transform: translateX(-50%) translateY(-6px); }
        }
        .animate-fade-out { animation: fadeOut 2.5s ease forwards; }
      `}</style>

      <div className="bg-[#0f0f0f] border border-white/10
                      rounded-t-2xl sm:rounded-2xl
                      w-full sm:max-w-5xl
                      h-[100dvh] sm:h-[94vh]
                      flex flex-col overflow-hidden shadow-2xl">

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/[0.07] shrink-0">
          <span className="text-white/60 text-xs font-medium truncate flex-1 min-w-0">{file.name}</span>

          {/* Tier badge */}
          <span className={`text-[10px] px-2 py-0.5 rounded-full border shrink-0 ${
            pageLimit === Infinity
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
          }`}>
            {tier} · {pageLimit === Infinity ? 'unlimited' : `${pageLimit} pg`}
          </span>

          <div className="w-px h-4 bg-white/10 shrink-0" />

          {/* Zoom */}
          <div className="flex items-center gap-0.5 shrink-0">
            <button onClick={() => zoom(-1)} className="w-8 h-8 flex items-center justify-center rounded-lg text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors">
              <ZoomOut size={14} />
            </button>
            <span className="text-[11px] text-white/30 w-10 text-center tabular-nums select-none">
              {Math.round(scale * 100)}%
            </span>
            <button onClick={() => zoom(1)} className="w-8 h-8 flex items-center justify-center rounded-lg text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors">
              <ZoomIn size={14} />
            </button>
            <button onClick={() => setScale(fitScale)} title="Fit to width"
              className="w-8 h-8 flex items-center justify-center rounded-lg text-white/35 hover:text-white/70 hover:bg-white/8 transition-colors">
              <Maximize2 size={13} />
            </button>
          </div>

          <div className="w-px h-4 bg-white/10 shrink-0" />
          <button onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors shrink-0">
            <X size={17} />
          </button>
        </div>


        {/* ── PDF viewport ────────────────────────────────────────────────────── */}
        <div ref={scrollRef} className="flex-1 overflow-auto bg-[#181818] min-h-0 relative" style={{ padding: '8px' }}>
          {/* Floating fade-away hint toast */}
          {showHint && !regionUrl && !loading && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 pointer-events-none
                            flex items-center gap-2 px-4 py-2 rounded-full
                            bg-black/70 border border-white/10 backdrop-blur-sm
                            animate-fade-out">
              <div className="w-1.5 h-1.5 rounded-full bg-violet-400 shrink-0" />
              <p className="text-white/70 text-xs whitespace-nowrap">Drag to capture any area</p>
            </div>
          )}
          {loading && (
            <div className="h-full flex items-center justify-center gap-2 text-white/35 text-sm">
              <Loader2 size={16} className="animate-spin" /> Loading PDF…
            </div>
          )}
          {error && (
            <div className="h-full flex items-center justify-center text-red-400 text-sm">{error}</div>
          )}
          {!loading && !error && (
            <div className="inline-block min-w-full">
              <div className="inline-block relative select-none"
                style={{ boxShadow: '0 2px 20px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05)' }}>
                <canvas ref={canvasRef} style={{ display: 'block' }} />

                {/* Crosshair region overlay */}
                <div
                  ref={overlayRef}
                  className="absolute inset-0"
                  style={{ cursor: regionUrl ? 'default' : 'crosshair', userSelect: 'none', touchAction: 'none' }}
                  onMouseDown={onMouseDown}
                  onMouseMove={onMouseMove}
                  onMouseUp={onMouseUp}
                  onMouseLeave={() => setDrawing(false)}
                >
                  {/* Selection rectangle while drawing */}
                  {selRect && (
                    <div
                      className="absolute border-2 border-violet-400 bg-violet-500/10 rounded-sm pointer-events-none"
                      style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h }}
                    />
                  )}

                  {/* Dim overlay with cut-out when region is captured */}
                  {regionUrl && selRect && (
                    <>
                      <div className="absolute inset-0 bg-black/40 pointer-events-none" />
                      <div
                        className="absolute border-2 border-violet-400 shadow-[0_0_0_9999px_rgba(0,0,0,0.4)] rounded-sm pointer-events-none"
                        style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h, background: 'transparent', boxShadow: 'none', outline: '9999px solid rgba(0,0,0,0.35)' }}
                      />
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Page navigation ─────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-white/[0.05] bg-[#0f0f0f] shrink-0">
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage <= 1}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-white/35 hover:text-white/65 disabled:opacity-20 hover:bg-white/5 transition-colors">
            <ChevronLeft size={15} />
          </button>
          <span className="text-xs text-white/35">
            Page {currentPage} / {effectiveMax || '…'}
            {numPages > pageLimit && <span className="ml-2 text-amber-400/50">{numPages - pageLimit} locked</span>}
          </span>
          <button onClick={() => setCurrentPage(p => Math.min(effectiveMax, p + 1))}
            disabled={currentPage >= effectiveMax || effectiveMax === 0}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-white/35 hover:text-white/65 disabled:opacity-20 hover:bg-white/5 transition-colors">
            <ChevronRight size={15} />
          </button>
        </div>

        {/* ── Action panel — only when region is captured ──────────────────────── */}
        {regionUrl && (
          <div className="border-t border-white/[0.07] bg-[#0f0f0f] shrink-0 px-3 py-3 flex flex-col gap-2">
            {/* Preview + clear */}
            <div className="flex items-center gap-2.5 bg-violet-500/10 border border-violet-500/20 rounded-xl px-3 py-2">
              <img src={regionUrl} alt="" className="h-9 object-contain rounded border border-violet-500/25 bg-white/5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-violet-300/80 font-medium">Region captured</p>
                <p className="text-[10px] text-violet-300/45 mt-0.5">Choose an action or ask a custom question</p>
              </div>
              <button onClick={clearRegion} className="text-white/25 hover:text-white/55 transition-colors shrink-0">
                <X size={13} />
              </button>
            </div>

            {/* Quick actions */}
            <div className="grid grid-cols-3 gap-2">
              <button onClick={() => fire('Explain this to me in simple terms')}
                className="flex items-center justify-center gap-1.5 py-3 rounded-xl
                           bg-violet-600 hover:bg-violet-500 active:bg-violet-700
                           text-white text-xs font-semibold transition-colors">
                <Lightbulb size={13} /> Explain
              </button>
              <button onClick={() => fire('Summarize this concisely')}
                className="flex items-center justify-center gap-1.5 py-3 rounded-xl
                           bg-white/[0.07] hover:bg-white/[0.12] active:bg-white/[0.04]
                           border border-white/[0.09] text-white/70 hover:text-white text-xs font-medium transition-colors">
                <AlignLeft size={13} /> Summarize
              </button>
              <button onClick={() => fire('What are the key points or takeaways from this?')}
                className="flex items-center justify-center gap-1.5 py-3 rounded-xl
                           bg-white/[0.07] hover:bg-white/[0.12] active:bg-white/[0.04]
                           border border-white/[0.09] text-white/70 hover:text-white text-xs font-medium transition-colors">
                <ListChecks size={13} /> Key points
              </button>
            </div>

            {/* Custom question */}
            {!showCustom ? (
              <button
                onClick={() => { setShowCustom(true); setTimeout(() => inputRef.current?.focus(), 50); }}
                className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl
                           border border-white/[0.08] text-white/35 hover:text-white/60
                           text-xs transition-colors hover:bg-white/[0.04] active:bg-white/[0.02]">
                <MessageSquare size={12} /> Ask your own question…
              </button>
            ) : (
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  value={customQ}
                  onChange={e => setCustomQ(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleCustomSend(); if (e.key === 'Escape') setShowCustom(false); }}
                  placeholder="Type your question about this region…"
                  className="flex-1 bg-[#1c1c1c] border border-white/10 rounded-xl px-3 py-2.5 text-sm
                             text-white placeholder-white/25 outline-none focus:border-violet-500/50 transition-colors"
                />
                <button onClick={handleCustomSend} disabled={!customQ.trim()}
                  className="px-4 py-2.5 rounded-xl text-sm font-medium flex items-center gap-1.5 shrink-0
                             bg-violet-600 hover:bg-violet-500 active:bg-violet-700
                             text-white disabled:opacity-35 transition-colors">
                  <Send size={13} />
                </button>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
