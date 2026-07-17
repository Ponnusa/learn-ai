'use client';
/**
 * StudyPDFPane — inline PDF panel for the study page split view.
 *
 * Sits beside the chat panel. Supports:
 *   • Region drag-select → image context (sent directly or pinned to chat input)
 *   • "This page" button → full-page image or extracted text (user toggles)
 *   • Ctrl+wheel zoom, fit-to-width, page navigation
 */
import { useState, useRef, useEffect } from 'react';
import {
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize2,
  X, Lightbulb, AlignLeft, ListChecks, Flame,
  MessageSquare, Send, Camera, FileText as FileTextIcon, Pin,
} from 'lucide-react';

const PDFJS_URL  = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const ZOOM_STEP  = 0.2;
const ZOOM_MIN   = 0.4;
const ZOOM_MAX   = 3.0;

interface Rect { x: number; y: number; w: number; h: number }
declare global { interface Window { pdfjsLib: any } }

export type PinnedCtx = {
  type: 'region' | 'page';
  mode: 'image' | 'text';
  imageDataUrl?: string;
  text?: string;
  pageNum: number;
};

interface StudyPDFPaneProps {
  file: File;
  onClose: () => void;
  /** Direct-fire: preset action selected from context menu */
  onFire: (prompt: string, imageDataUrl?: string) => void;
  /** Pin region/page to chat input so user can type their own question */
  onPin: (ctx: PinnedCtx) => void;
}

export function StudyPDFPane({ file, onClose, onFire, onPin }: StudyPDFPaneProps) {
  const scrollRef  = useRef<HTMLDivElement>(null);
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const inputRef   = useRef<HTMLInputElement>(null);

  const [pdfDoc,      setPdfDoc]      = useState<any>(null);
  const [numPages,    setNumPages]    = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale,       setScale]       = useState(1.0);
  const [fitScale,    setFitScale]    = useState(1.0);
  const [loadState,   setLoadState]   = useState<'loading' | 'ready' | 'error'>('loading');
  const [loadError,   setLoadError]   = useState('');
  const [showHint,    setShowHint]    = useState(true);

  // Region drawing
  const [drawing,   setDrawing]   = useState(false);
  const [startPos,  setStartPos]  = useState<{ x: number; y: number } | null>(null);
  const [selRect,   setSelRect]   = useState<Rect | null>(null);
  const [regionUrl, setRegionUrl] = useState<string | null>(null);
  const [menuPos,   setMenuPos]   = useState<{ x: number; y: number } | null>(null);
  const [customQ,   setCustomQ]   = useState('');
  const [showCustom, setShowCustom] = useState(false);

  // Context mode toggle for "This page"
  const [ctxMode, setCtxMode] = useState<'image' | 'text'>('image');

  // Refs for non-passive touch handlers
  const drawingRef  = useRef(false);
  const startRef    = useRef<{ x: number; y: number } | null>(null);
  const selRectRef  = useRef<Rect | null>(null);
  drawingRef.current = drawing;
  startRef.current   = startPos;
  selRectRef.current = selRect;

  // ── Load PDF.js + document ────────────────────────────────────────────────
  useEffect(() => {
    async function init() {
      try {
        if (!window.pdfjsLib) {
          await new Promise<void>((resolve, reject) => {
            const s = document.createElement('script');
            s.src = PDFJS_URL;
            s.onload = () => resolve();
            s.onerror = () => reject(new Error('Failed to load PDF.js'));
            document.head.appendChild(s);
          });
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_URL;
        }
        const doc = await window.pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
      } catch (e: any) {
        setLoadError(e.message || 'Failed to load PDF');
        setLoadState('error');
      }
    }
    init();
  }, [file]);

  // ── Fit scale ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc) return;
    requestAnimationFrame(async () => {
      try {
        const page   = await pdfDoc.getPage(1);
        const natVp  = page.getViewport({ scale: 1 });
        const availW = (scrollRef.current?.clientWidth ?? 500) - 16;
        const fit    = parseFloat(Math.min(availW / natVp.width, ZOOM_MAX).toFixed(2));
        setFitScale(fit);
        setScale(fit);
      } catch { /* use default */ }
      setLoadState('ready');
      setTimeout(() => setShowHint(false), 2500);
    });
  }, [pdfDoc]);

  // ── DPR-aware render ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current || loadState !== 'ready') return;
    let cancelled = false;
    let task: any  = null;
    async function render() {
      try {
        const page    = await pdfDoc.getPage(currentPage);
        if (cancelled) return;
        const dpr     = window.devicePixelRatio || 1;
        const baseVp  = page.getViewport({ scale });
        const hiVp    = page.getViewport({ scale: scale * dpr });
        const canvas  = canvasRef.current!;
        canvas.width  = hiVp.width;
        canvas.height = hiVp.height;
        canvas.style.width  = `${baseVp.width}px`;
        canvas.style.height = `${baseVp.height}px`;
        task = page.render({ canvasContext: canvas.getContext('2d')!, viewport: hiVp });
        await task.promise;
      } catch { }
    }
    clearRegion();
    render();
    return () => { cancelled = true; task?.cancel?.(); };
  }, [pdfDoc, currentPage, scale, loadState]);

  // ── Non-passive touch handlers ────────────────────────────────────────────
  useEffect(() => {
    const el = overlayRef.current; if (!el) return;
    const getPos = (touch: Touch) => {
      const r = el.getBoundingClientRect();
      return { x: touch.clientX - r.left, y: touch.clientY - r.top };
    };
    const ts = (e: TouchEvent) => {
      e.preventDefault();
      const pos = getPos(e.touches[0]);
      startRef.current = pos; setStartPos(pos);
      setDrawing(true); drawingRef.current = true;
      setSelRect(null); selRectRef.current = null; setRegionUrl(null);
    };
    const tm = (e: TouchEvent) => {
      e.preventDefault();
      if (!drawingRef.current || !startRef.current) return;
      const { x, y } = getPos(e.touches[0]);
      const r = { x: Math.min(startRef.current.x, x), y: Math.min(startRef.current.y, y), w: Math.abs(x - startRef.current.x), h: Math.abs(y - startRef.current.y) };
      selRectRef.current = r; setSelRect(r);
    };
    const te = (e: TouchEvent) => {
      e.preventDefault();
      setDrawing(false); drawingRef.current = false;
      const r = selRectRef.current;
      if (r && r.w > 10 && r.h > 10) extractRegion(r);
    };
    el.addEventListener('touchstart', ts, { passive: false });
    el.addEventListener('touchmove',  tm, { passive: false });
    el.addEventListener('touchend',   te, { passive: false });
    return () => { el.removeEventListener('touchstart', ts); el.removeEventListener('touchmove', tm); el.removeEventListener('touchend', te); };
  }, []);

  // ── Ctrl+wheel zoom ───────────────────────────────────────────────────────
  useEffect(() => {
    const el = scrollRef.current; if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setScale(s => parseFloat(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP))).toFixed(2)));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  // ── Mouse region ──────────────────────────────────────────────────────────
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
    off.getContext('2d')!.drawImage(canvas, Math.round(rect.x * sx), Math.round(rect.y * sy), off.width, off.height, 0, 0, off.width, off.height);
    setRegionUrl(off.toDataURL('image/png'));
    const cb = canvas.getBoundingClientRect();
    setMenuPos({ x: cb.left + rect.x + rect.w / 2, y: cb.top + rect.y + rect.h + 12 });
  }

  function clearRegion() { setSelRect(null); setRegionUrl(null); setMenuPos(null); setCustomQ(''); setShowCustom(false); }

  function fire(prompt: string) { onFire(prompt, regionUrl ?? undefined); clearRegion(); }

  async function handleThisPage() {
    if (!pdfDoc) return;
    if (ctxMode === 'text') {
      try {
        const page = await pdfDoc.getPage(currentPage);
        const tc   = await page.getTextContent();
        const text = (tc.items as any[]).map(i => i.str || '').join(' ').replace(/\s+/g, ' ').trim();
        onPin({ type: 'page', mode: 'text', text, pageNum: currentPage });
      } catch { }
    } else {
      const canvas = canvasRef.current; if (!canvas) return;
      const off  = document.createElement('canvas');
      off.width  = canvas.width;
      off.height = canvas.height;
      off.getContext('2d')!.drawImage(canvas, 0, 0);
      onPin({ type: 'page', mode: 'image', imageDataUrl: off.toDataURL('image/png'), pageNum: currentPage });
    }
  }

  function zoom(dir: 1 | -1) {
    setScale(s => parseFloat(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s + dir * ZOOM_STEP)).toFixed(2)));
  }

  const canGoBack = currentPage > 1;
  const canGoFwd  = currentPage < numPages;

  return (
    <div className="flex flex-col h-full bg-[#111] select-none" style={{ minHeight: 0 }}>
      <style>{`
        @keyframes pdfHintOut {
          0%,70% { opacity:1; transform:translateX(-50%) translateY(0); }
          100%    { opacity:0; transform:translateX(-50%) translateY(-6px); }
        }
        .pdf-hint-out { animation: pdfHintOut 2.5s ease forwards; }
        @keyframes pdfCtxIn { from{opacity:0;transform:scale(0.92)} to{opacity:1;transform:scale(1)} }
      `}</style>

      {/* ── Toolbar ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-white/[0.07] shrink-0">
        <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={!canGoBack}
          className="w-7 h-7 flex items-center justify-center rounded-md text-white/40 hover:text-white/80
                     disabled:opacity-20 hover:bg-white/8 transition-colors shrink-0">
          <ChevronLeft size={14} />
        </button>
        <span className="text-[11px] text-white/40 tabular-nums select-none w-12 text-center shrink-0">
          {numPages ? `${currentPage}/${numPages}` : '…'}
        </span>
        <button onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))} disabled={!canGoFwd}
          className="w-7 h-7 flex items-center justify-center rounded-md text-white/40 hover:text-white/80
                     disabled:opacity-20 hover:bg-white/8 transition-colors shrink-0">
          <ChevronRight size={14} />
        </button>

        <div className="w-px h-3.5 bg-white/10 mx-0.5 shrink-0" />

        <button onClick={() => zoom(-1)} className="w-7 h-7 flex items-center justify-center rounded-md text-white/35 hover:text-white/70 hover:bg-white/8 transition-colors shrink-0">
          <ZoomOut size={12} />
        </button>
        <span className="text-[10px] text-white/25 w-8 text-center tabular-nums shrink-0">{Math.round(scale * 100)}%</span>
        <button onClick={() => zoom(1)} className="w-7 h-7 flex items-center justify-center rounded-md text-white/35 hover:text-white/70 hover:bg-white/8 transition-colors shrink-0">
          <ZoomIn size={12} />
        </button>
        <button onClick={() => setScale(fitScale)} title="Fit to width"
          className="w-7 h-7 flex items-center justify-center rounded-md text-white/25 hover:text-white/60 hover:bg-white/8 transition-colors shrink-0">
          <Maximize2 size={11} />
        </button>

        <span className="flex-1 min-w-0 text-[10px] text-white/20 truncate mx-1">{file.name}</span>

        <button onClick={onClose} title="Hide PDF"
          className="w-7 h-7 flex items-center justify-center rounded-md text-white/30 hover:text-white/60 hover:bg-white/8 transition-colors shrink-0">
          <X size={14} />
        </button>
      </div>

      {/* ── Canvas area ─────────────────────────────────────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-auto bg-[#181818] min-h-0 relative" style={{ padding: '6px' }}>
        {showHint && loadState === 'ready' && !regionUrl && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 pointer-events-none
                          flex items-center gap-2 px-3 py-1.5 rounded-full
                          bg-black/70 border border-white/10 backdrop-blur-sm pdf-hint-out">
            <div className="w-1.5 h-1.5 rounded-full bg-violet-400 shrink-0" />
            <p className="text-white/65 text-[11px] whitespace-nowrap">Drag to select a region</p>
          </div>
        )}

        {loadState === 'loading' && (
          <div className="h-full flex items-center justify-center text-white/30 text-sm gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-violet-500/40 border-t-violet-400 animate-spin" />
            Loading…
          </div>
        )}
        {loadState === 'error' && (
          <div className="h-full flex items-center justify-center text-red-400/70 text-sm px-4 text-center">{loadError}</div>
        )}

        {loadState === 'ready' && (
          <div className="inline-block min-w-full">
            <div className="inline-block relative"
              style={{ boxShadow: '0 2px 16px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)' }}>
              <canvas ref={canvasRef} style={{ display: 'block' }} />

              {/* Drawing overlay */}
              <div
                ref={overlayRef}
                className="absolute inset-0"
                style={{ cursor: regionUrl ? 'default' : 'crosshair', touchAction: 'none' }}
                onMouseDown={onMouseDown}
                onMouseMove={onMouseMove}
                onMouseUp={onMouseUp}
                onMouseLeave={() => setDrawing(false)}
              >
                {selRect && !regionUrl && (
                  <div className="absolute border-2 border-violet-400 bg-violet-500/10 rounded-sm pointer-events-none"
                    style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h }} />
                )}
                {regionUrl && selRect && (
                  <>
                    <div className="absolute inset-0 bg-black/40 pointer-events-none" />
                    <div className="absolute border-2 border-violet-400 rounded-sm pointer-events-none"
                      style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h,
                               background: 'transparent', outline: '9999px solid rgba(0,0,0,0.40)' }} />
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Footer: context mode + "This page" ──────────────────────── */}
      {loadState === 'ready' && (
        <div className="flex items-center gap-2 px-3 py-2 border-t border-white/[0.07] shrink-0">
          {/* Image / Text toggle */}
          <div className="flex items-center gap-0 rounded-lg border border-white/10 overflow-hidden shrink-0">
            <button
              onClick={() => setCtxMode('image')}
              className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium transition-colors
                ${ctxMode === 'image' ? 'bg-violet-600/30 text-violet-300' : 'text-white/30 hover:text-white/55 hover:bg-white/5'}`}>
              <Camera size={11} /> Snapshot
            </button>
            <div className="w-px h-4 bg-white/10" />
            <button
              onClick={() => setCtxMode('text')}
              className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium transition-colors
                ${ctxMode === 'text' ? 'bg-indigo-600/30 text-indigo-300' : 'text-white/30 hover:text-white/55 hover:bg-white/5'}`}>
              <FileTextIcon size={11} /> Text
            </button>
          </div>

          <button
            onClick={handleThisPage}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium
                       bg-white/5 hover:bg-white/10 text-white/55 hover:text-white/80 transition-colors shrink-0">
            <Pin size={11} /> This page
          </button>

          <span className="text-[10px] text-white/20 flex-1 text-right truncate">
            {ctxMode === 'image' ? 'Sends page as image' : 'Extracts page text'}
          </span>
        </div>
      )}

      {/* ── Context menu (fixed to viewport) ────────────────────────── */}
      {regionUrl && menuPos && (() => {
        const W  = 200;
        const vw = typeof window !== 'undefined' ? window.innerWidth  : 800;
        const vh = typeof window !== 'undefined' ? window.innerHeight : 600;
        const cx = Math.max(8, Math.min(vw - W - 8, menuPos.x - W / 2));
        const cy = menuPos.y + 280 < vh ? menuPos.y : menuPos.y - 280 - (selRect?.h ?? 0) - 24;
        return (
          <div
            className="fixed z-[60] bg-[#1c1c1e] border border-white/[0.13] rounded-2xl shadow-2xl overflow-hidden"
            style={{ left: cx, top: Math.max(8, Math.min(vh - 280, cy)), width: W, animation: 'pdfCtxIn 0.13s ease' }}
            onMouseDown={e => e.stopPropagation()}
          >
            {/* Primary */}
            <button onClick={() => fire('Explain this to me in simple terms')}
              className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-semibold
                         text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 transition-colors">
              <Lightbulb size={13} className="shrink-0" /> Explain
            </button>
            <div className="h-px bg-white/[0.07]" />
            <button onClick={() => fire('Summarize this concisely')}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium
                         text-white/60 hover:text-white hover:bg-white/[0.07] transition-colors">
              <AlignLeft size={12} className="shrink-0" /> Summarize
            </button>
            <button onClick={() => fire('What are the key points from this?')}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium
                         text-white/60 hover:text-white hover:bg-white/[0.07] transition-colors">
              <ListChecks size={12} className="shrink-0" /> Key points
            </button>
            <button onClick={() => fire('Brainstorm questions I should explore based on this')}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium
                         text-white/60 hover:text-white hover:bg-white/[0.07] transition-colors">
              <Flame size={12} className="shrink-0" /> Brainstorm
            </button>
            <div className="h-px bg-white/[0.07]" />
            {/* Pin to chat — user types own question */}
            <button onClick={() => {
              onPin({ type: 'region', mode: 'image', imageDataUrl: regionUrl!, pageNum: currentPage });
              clearRegion();
            }}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium
                         text-indigo-300/70 hover:text-indigo-300 hover:bg-indigo-500/10 transition-colors">
              <Pin size={12} className="shrink-0" /> Pin to chat input
            </button>
            <div className="h-px bg-white/[0.07]" />
            {/* Ask custom */}
            {!showCustom ? (
              <button onClick={() => { setShowCustom(true); setTimeout(() => inputRef.current?.focus(), 40); }}
                className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium
                           text-white/35 hover:text-white/60 hover:bg-white/[0.05] transition-colors">
                <MessageSquare size={12} className="shrink-0" /> Ask your own…
              </button>
            ) : (
              <div className="flex gap-1.5 px-2 py-2">
                <input ref={inputRef} value={customQ} onChange={e => setCustomQ(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && customQ.trim()) { fire(customQ.trim()); } if (e.key === 'Escape') setShowCustom(false); }}
                  placeholder="Ask anything…"
                  className="flex-1 bg-white/[0.06] border border-white/10 rounded-lg px-2.5 py-1.5
                             text-xs text-white placeholder-white/25 outline-none
                             focus:border-violet-500/50 transition-colors min-w-0" />
                <button onClick={() => { if (customQ.trim()) fire(customQ.trim()); }}
                  disabled={!customQ.trim()}
                  className="w-7 h-7 flex items-center justify-center rounded-lg shrink-0
                             bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-30 transition-colors">
                  <Send size={11} />
                </button>
              </div>
            )}
            <div className="h-px bg-white/[0.07]" />
            <button onClick={clearRegion}
              className="w-full flex items-center gap-2 px-4 py-1.5 text-[10px]
                         text-white/22 hover:text-white/45 hover:bg-white/[0.04] transition-colors">
              <X size={10} className="shrink-0" /> Clear selection
            </button>
          </div>
        );
      })()}
    </div>
  );
}
