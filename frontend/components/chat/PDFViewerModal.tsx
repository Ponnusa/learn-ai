'use client';
/**
 * PDFViewerModal
 * - Canvas renders at scale × devicePixelRatio (crisp on HiDPI/Retina)
 * - Text layer uses CSS-scale viewport so selection positions stay correct
 * - Fit scale computed after first paint via rAF so clientWidth is reliable
 * - Fits to container WIDTH; vertical scrolling for tall pages
 */
import { useState, useRef, useEffect } from 'react';
import {
  X, ZoomIn, ZoomOut, MousePointer, Crop,
  ChevronLeft, ChevronRight, Send, Loader2,
  Lightbulb, AlignLeft, ListChecks, MessageSquare, Sparkles, Maximize2,
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

type Mode = 'text' | 'region';
interface Rect { x: number; y: number; w: number; h: number }
declare global { interface Window { pdfjsLib: any } }

interface PDFViewerModalProps {
  file: File;
  onClose: () => void;
  onAsk: (question: string, context: { text?: string; imageDataUrl?: string }) => void;
}

export function PDFViewerModal({ file, onClose, onAsk }: PDFViewerModalProps) {
  const { user } = useSessionStore();
  const tier      = user?.tier ?? 'anonymous';
  const pageLimit = PAGE_LIMITS[tier] ?? 2;

  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const scrollRef    = useRef<HTMLDivElement>(null);
  const inputRef     = useRef<HTMLInputElement>(null);

  const [pdfDoc,       setPdfDoc]       = useState<any>(null);
  const [numPages,     setNumPages]     = useState(0);
  const [currentPage,  setCurrentPage]  = useState(1);
  const [scale,        setScale]        = useState(1.0);
  const [fitScale,     setFitScale]     = useState(1.0);
  const [mode,         setMode]         = useState<Mode>('text');
  const [pageText,     setPageText]     = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [regionUrl,    setRegionUrl]    = useState<string | null>(null);
  const [customQ,      setCustomQ]      = useState('');
  const [showCustom,   setShowCustom]   = useState(false);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState('');

  const [drawing,  setDrawing]  = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [selRect,  setSelRect]  = useState<Rect | null>(null);

  const effectiveMax = numPages > 0 ? Math.min(numPages, pageLimit) : 0;
  const hasSelection = mode === 'text' ? !!selectedText : !!regionUrl;

  // ── Load PDF.js + document ───────────────────────────────────────────────────
  // Keep loading=true; fit-scale effect will setLoading(false) after first paint.
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
        // loading stays true — cleared by the fit-scale effect below
      } catch (e: any) {
        setError(e.message || 'Failed to load PDF');
        setLoading(false);
      }
    }
    init();
  }, [file]);

  // ── Compute fit scale after first paint so clientWidth is real ───────────────
  useEffect(() => {
    if (!pdfDoc) return;
    // rAF ensures the modal is fully painted and scrollRef has real dimensions
    const raf = requestAnimationFrame(async () => {
      try {
        const page      = await pdfDoc.getPage(1);
        const naturalVp = page.getViewport({ scale: 1 });
        const container = scrollRef.current;
        // Fit to available width only; let height scroll
        const availW    = (container?.clientWidth ?? 640) - 16; // 8px padding each side
        const fit       = parseFloat(Math.min(availW / naturalVp.width, ZOOM_MAX).toFixed(2));
        setFitScale(fit);
        setScale(fit);
      } catch { /* use default */ }
      setLoading(false);
    });
    return () => cancelAnimationFrame(raf);
  }, [pdfDoc]);

  // ── DPR-aware page render ────────────────────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current || !textLayerRef.current) return;
    let cancelled = false;
    let renderTask: any = null;
    let textTask: any   = null;

    async function render() {
      try {
        const page    = await pdfDoc.getPage(currentPage);
        if (cancelled) return;

        const dpr     = window.devicePixelRatio || 1;
        const baseVp  = page.getViewport({ scale });             // CSS pixels
        const hiDpiVp = page.getViewport({ scale: scale * dpr }); // physical pixels

        const canvas  = canvasRef.current!;
        const tl      = textLayerRef.current!;

        // Physical canvas (sharp)
        canvas.width  = hiDpiVp.width;
        canvas.height = hiDpiVp.height;
        // CSS display size (correct scale)
        canvas.style.width  = `${baseVp.width}px`;
        canvas.style.height = `${baseVp.height}px`;

        renderTask = page.render({ canvasContext: canvas.getContext('2d')!, viewport: hiDpiVp });
        await renderTask.promise;
        if (cancelled) return;

        // Text layer uses baseVp so span positions match CSS coords
        tl.innerHTML    = '';
        tl.style.width  = `${baseVp.width}px`;
        tl.style.height = `${baseVp.height}px`;

        const textContent = await page.getTextContent();
        if (cancelled) return;
        setPageText(textContent.items.map((i: any) => i.str).filter((s: string) => s.trim()).join(' '));

        textTask = window.pdfjsLib.renderTextLayer({ textContent, container: tl, viewport: baseVp, textDivs: [] });
        await textTask.promise;
      } catch { /* cancelled / non-fatal */ }
    }

    clearSelection();
    render();
    return () => { cancelled = true; renderTask?.cancel?.(); textTask?.cancel?.(); };
  }, [pdfDoc, currentPage, scale]);

  // ── Ctrl/Cmd + wheel zoom ────────────────────────────────────────────────────
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    function onWheel(e: WheelEvent) {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const delta = e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
      setScale(s => parseFloat(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s + delta)).toFixed(2)));
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  // ── Region drawing ────────────────────────────────────────────────────────────
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

  function clearSelection() {
    setSelRect(null); setRegionUrl(null); setSelectedText('');
    setCustomQ(''); setShowCustom(false);
    window.getSelection()?.removeAllRanges();
  }
  function switchMode(m: Mode) { setMode(m); clearSelection(); }
  function fire(prompt: string) {
    if (mode === 'text') onAsk(prompt, { text: selectedText || pageText.slice(0, 2000) || undefined });
    else                 onAsk(prompt, { imageDataUrl: regionUrl ?? undefined });
  }
  function handleCustomSend() { const q = customQ.trim(); if (!q) return; fire(q); }
  function zoom(dir: 1 | -1) {
    setScale(s => parseFloat(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s + dir * ZOOM_STEP)).toFixed(2)));
  }

  // ────────────────────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm sm:p-3">
      <style>{`
        .pdf-tl { position:absolute; top:0; left:0; overflow:hidden; line-height:1; }
        .pdf-tl span { color:transparent; position:absolute; white-space:pre; cursor:text; transform-origin:0% 0%; }
        .pdf-tl span::selection { background:rgba(139,92,246,0.4); color:transparent; }
        .pdf-tl br { display:none; }
      `}</style>

      {/* Sheet: full-screen on mobile, large modal on sm+ */}
      <div className="bg-[#0f0f0f] border border-white/10
                      rounded-t-2xl sm:rounded-2xl
                      w-full sm:max-w-5xl
                      h-[100dvh] sm:h-[94vh]
                      flex flex-col overflow-hidden shadow-2xl">

        {/* ── Compact single-row header ───────────────────────────────────────── */}
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/[0.07] shrink-0">
          {/* Mode toggle */}
          <div className="flex gap-0.5 p-0.5 rounded-lg bg-white/[0.05] border border-white/[0.07] shrink-0">
            <button onClick={() => switchMode('text')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-[7px] text-[11px] font-medium transition-all ${
                mode === 'text' ? 'bg-violet-600 text-white' : 'text-white/45 hover:text-white/70'
              }`}>
              <MousePointer size={10} />
              <span className="hidden xs:inline">Text</span>
            </button>
            <button onClick={() => switchMode('region')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-[7px] text-[11px] font-medium transition-all ${
                mode === 'region' ? 'bg-violet-600 text-white' : 'text-white/45 hover:text-white/70'
              }`}>
              <Crop size={10} />
              <span className="hidden xs:inline">Region</span>
            </button>
          </div>

          {/* Filename */}
          <span className="text-white/60 text-xs truncate flex-1 min-w-0">{file.name}</span>

          {/* Zoom controls */}
          <div className="flex items-center gap-0.5 shrink-0">
            <button onClick={() => zoom(-1)}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors">
              <ZoomOut size={14} />
            </button>
            <span className="text-[11px] text-white/35 w-9 text-center tabular-nums select-none">
              {Math.round(scale * 100)}%
            </span>
            <button onClick={() => zoom(1)}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors">
              <ZoomIn size={14} />
            </button>
            <button onClick={() => setScale(fitScale)} title="Fit to width"
              className="w-7 h-7 flex items-center justify-center rounded-lg text-white/35 hover:text-white/70 hover:bg-white/8 transition-colors">
              <Maximize2 size={12} />
            </button>
          </div>

          <div className="w-px h-4 bg-white/10 shrink-0" />
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors shrink-0">
            <X size={16} />
          </button>
        </div>

        {/* ── PDF viewport — fills all remaining space ────────────────────────── */}
        <div ref={scrollRef}
          className="flex-1 overflow-auto bg-[#181818] min-h-0"
          style={{ padding: '8px' }}>
          {loading && (
            <div className="h-full flex items-center justify-center gap-2 text-white/35 text-sm">
              <Loader2 size={16} className="animate-spin" /> Loading PDF…
            </div>
          )}
          {error && (
            <div className="h-full flex items-center justify-center text-red-400 text-sm">{error}</div>
          )}
          {!loading && !error && (
            // Canvas wrapper fills container width; canvas CSS width set by render effect
            <div className="relative inline-block min-w-full">
              <div className="inline-block relative select-none"
                style={{ boxShadow: '0 2px 24px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05)' }}>
                <canvas ref={canvasRef} style={{ display: 'block' }} />

                {/* Invisible text layer for native selection */}
                <div
                  ref={textLayerRef}
                  className="pdf-tl"
                  style={{ pointerEvents: mode === 'text' ? 'auto' : 'none' }}
                  onMouseUp={() => {
                    const sel = window.getSelection()?.toString().trim();
                    if (sel) setSelectedText(sel);
                  }}
                />

                {/* Region crosshair overlay */}
                {mode === 'region' && (
                  <div
                    className="absolute inset-0"
                    style={{ cursor: 'crosshair', userSelect: 'none' }}
                    onMouseDown={onMouseDown}
                    onMouseMove={onMouseMove}
                    onMouseUp={onMouseUp}
                    onMouseLeave={() => setDrawing(false)}
                  >
                    {selRect && (
                      <div
                        className="absolute border-2 border-violet-400 bg-violet-500/10 rounded-sm pointer-events-none"
                        style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h }}
                      />
                    )}
                    {!selRect && !regionUrl && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <span className="bg-black/70 text-white/50 text-xs px-3 py-1.5 rounded-full border border-white/10">
                          Drag to select a region
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Page navigation ─────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-white/[0.05] bg-[#0f0f0f] shrink-0">
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage <= 1}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-white/35
                       hover:text-white/65 disabled:opacity-20 hover:bg-white/5 transition-colors">
            <ChevronLeft size={15} />
          </button>
          <div className="flex items-center gap-3">
            <span className="text-xs text-white/35">
              Page {currentPage} / {effectiveMax || '…'}
            </span>
            {numPages > pageLimit && (
              <span className="text-[10px] text-amber-400/50">{numPages - pageLimit} locked</span>
            )}
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${
              pageLimit === Infinity
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
            }`}>
              {tier}
            </span>
          </div>
          <button onClick={() => setCurrentPage(p => Math.min(effectiveMax, p + 1))}
            disabled={currentPage >= effectiveMax || effectiveMax === 0}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-white/35
                       hover:text-white/65 disabled:opacity-20 hover:bg-white/5 transition-colors">
            <ChevronRight size={15} />
          </button>
        </div>

        {/* ── Action panel — only shown when selection exists ──────────────────── */}
        {hasSelection && (
          <div className="border-t border-white/[0.07] bg-[#0f0f0f] shrink-0 px-3 py-3 flex flex-col gap-2">
            {/* Selection preview */}
            <div className="flex items-center gap-2 bg-violet-500/10 border border-violet-500/20 rounded-xl px-3 py-1.5">
              {selectedText ? (
                <>
                  <Sparkles size={11} className="text-violet-400 shrink-0" />
                  <span className="text-xs text-violet-300/80 flex-1 truncate">
                    "{selectedText.length > 90 ? selectedText.slice(0, 90) + '…' : selectedText}"
                  </span>
                </>
              ) : (
                <>
                  <Crop size={11} className="text-violet-400 shrink-0" />
                  <img src={regionUrl!} alt="" className="h-7 object-contain rounded border border-violet-500/25 bg-white/5 shrink-0" />
                  <span className="text-xs text-violet-300/60 flex-1">Region captured</span>
                </>
              )}
              <button onClick={clearSelection} className="text-white/25 hover:text-white/55 transition-colors ml-auto shrink-0">
                <X size={12} />
              </button>
            </div>

            {/* Quick-action row */}
            <div className="grid grid-cols-3 gap-2">
              <button onClick={() => fire('Explain this to me in simple terms')}
                className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl
                           bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors">
                <Lightbulb size={13} /> Explain
              </button>
              <button onClick={() => fire('Summarize this concisely')}
                className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl
                           bg-white/[0.07] hover:bg-white/[0.12] border border-white/[0.09]
                           text-white/70 hover:text-white text-xs font-medium transition-colors">
                <AlignLeft size={13} /> Summarize
              </button>
              <button onClick={() => fire('What are the key points or takeaways from this?')}
                className="flex items-center justify-center gap-1.5 py-2.5 rounded-xl
                           bg-white/[0.07] hover:bg-white/[0.12] border border-white/[0.09]
                           text-white/70 hover:text-white text-xs font-medium transition-colors">
                <ListChecks size={13} /> Key points
              </button>
            </div>

            {/* Custom question */}
            {!showCustom ? (
              <button
                onClick={() => { setShowCustom(true); setTimeout(() => inputRef.current?.focus(), 50); }}
                className="flex items-center justify-center gap-1.5 py-2 rounded-xl
                           border border-white/[0.08] text-white/35 hover:text-white/60
                           text-xs transition-colors hover:bg-white/[0.04]">
                <MessageSquare size={11} /> Ask your own question…
              </button>
            ) : (
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  value={customQ}
                  onChange={e => setCustomQ(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleCustomSend(); if (e.key === 'Escape') setShowCustom(false); }}
                  placeholder="Type your question…"
                  className="flex-1 bg-[#1c1c1c] border border-white/10 rounded-xl px-3 py-2 text-sm
                             text-white placeholder-white/25 outline-none focus:border-violet-500/50 transition-colors"
                />
                <button onClick={handleCustomSend} disabled={!customQ.trim()}
                  className="px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-1.5 shrink-0
                             bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-35 transition-colors">
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
