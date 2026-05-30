'use client';
/**
 * PDFViewerModal
 *
 * PDF.js v3 loaded from CDN at runtime (zero webpack bundle).
 * Canvas renders at scale × devicePixelRatio for crisp output on any display.
 * Text layer uses the CSS-scale viewport so selection positions are correct.
 * Initial scale is auto-computed to fill the viewer width.
 */
import { useState, useRef, useEffect, useCallback } from 'react';
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

  const canvasRef       = useRef<HTMLCanvasElement>(null);
  const textLayerRef    = useRef<HTMLDivElement>(null);
  const scrollRef       = useRef<HTMLDivElement>(null);   // pdf viewport container
  const inputRef        = useRef<HTMLInputElement>(null);

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

  // Region drawing
  const [drawing,  setDrawing]  = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [selRect,  setSelRect]  = useState<Rect | null>(null);

  const effectiveMax = numPages > 0 ? Math.min(numPages, pageLimit) : 0;
  const hasSelection  = mode === 'text' ? !!selectedText : !!regionUrl;

  // ── Load PDF.js + open file, compute fit scale before first render ───────────
  useEffect(() => {
    async function init() {
      try {
        if (!window.pdfjsLib) {
          await new Promise<void>((resolve, reject) => {
            const s = document.createElement('script');
            s.src = PDFJS_URL; s.onload = () => resolve();
            s.onerror = () => reject(new Error('Failed to load PDF.js'));
            document.head.appendChild(s);
          });
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_URL;
        }

        const data = await file.arrayBuffer();
        const doc  = await window.pdfjsLib.getDocument({ data }).promise;

        // Compute fit-to-width scale from page 1 before the first render
        try {
          const p1          = await doc.getPage(1);
          const naturalVp   = p1.getViewport({ scale: 1 });
          const container   = scrollRef.current;
          const availW      = container ? container.clientWidth  - 48 : 600;
          const availH      = container ? container.clientHeight - 48 : 700;
          const fit = parseFloat(
            Math.min(availW / naturalVp.width, availH / naturalVp.height, 2.0).toFixed(2)
          );
          setFitScale(fit);
          setScale(fit);
        } catch { /* use default */ }

        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setLoading(false);
      } catch (e: any) {
        setError(e.message || 'Failed to load PDF');
        setLoading(false);
      }
    }
    init();
  }, [file]);

  // ── DPR-aware page render ────────────────────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current || !textLayerRef.current) return;
    let cancelled    = false;
    let renderTask: any = null;
    let textTask: any   = null;

    async function render() {
      try {
        const page        = await pdfDoc.getPage(currentPage);
        if (cancelled) return;

        const dpr         = window.devicePixelRatio || 1;
        const baseVp      = page.getViewport({ scale });           // CSS-pixel viewport
        const hiDpiVp     = page.getViewport({ scale: scale * dpr }); // physical-pixel viewport

        const canvas      = canvasRef.current!;
        const tl          = textLayerRef.current!;

        // Physical canvas = rendered at full DPI
        canvas.width      = hiDpiVp.width;
        canvas.height     = hiDpiVp.height;
        // CSS size = what the user sees (matches baseVp)
        canvas.style.width  = `${baseVp.width}px`;
        canvas.style.height = `${baseVp.height}px`;

        const ctx = canvas.getContext('2d')!;
        renderTask = page.render({ canvasContext: ctx, viewport: hiDpiVp });
        await renderTask.promise;
        if (cancelled) return;

        // Text layer — positioned using baseVp so selection coords match CSS
        tl.innerHTML     = '';
        tl.style.width   = `${baseVp.width}px`;
        tl.style.height  = `${baseVp.height}px`;

        const textContent = await page.getTextContent();
        if (cancelled) return;

        setPageText(textContent.items.map((i: any) => i.str).filter((s: string) => s.trim()).join(' '));

        textTask = window.pdfjsLib.renderTextLayer({
          textContent,
          container: tl,
          viewport:  baseVp,   // ← base viewport keeps span positions correct
          textDivs:  [],
        });
        await textTask.promise;
      } catch { /* cancelled or non-fatal */ }
    }

    clearSelection();
    render();
    return () => {
      cancelled = true;
      renderTask?.cancel?.();
      textTask?.cancel?.();
    };
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
    // sx/sy naturally equal devicePixelRatio because canvas.width is hi-DPI
    // while canvas.offsetWidth is the CSS display width
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
  function handleCustomSend() {
    const q = customQ.trim(); if (!q) return; fire(q);
  }

  function zoom(dir: 1 | -1) {
    setScale(s => parseFloat(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s + dir * ZOOM_STEP)).toFixed(2)));
  }

  // ────────────────────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm sm:p-4">
      <style>{`
        .pdf-tl { position:absolute; top:0; left:0; overflow:hidden; line-height:1; }
        .pdf-tl span {
          color: transparent; position: absolute; white-space: pre;
          cursor: text; transform-origin: 0% 0%;
        }
        .pdf-tl span::selection { background: rgba(139,92,246,0.4); color: transparent; }
        .pdf-tl br { display: none; }
      `}</style>

      <div className="bg-[#0f0f0f] border border-white/10 rounded-t-3xl sm:rounded-2xl
                      w-full sm:max-w-4xl h-[96vh] sm:h-[92vh]
                      flex flex-col overflow-hidden shadow-2xl">

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div className="flex flex-col gap-2 px-4 pt-4 pb-3 border-b border-white/[0.07] shrink-0">
          {/* Row 1: filename + zoom + close */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-violet-500/15 border border-violet-500/25 flex items-center justify-center shrink-0">
                <AlignLeft size={13} className="text-violet-400" />
              </div>
              <span className="text-white/85 font-medium text-sm truncate">{file.name}</span>
            </div>

            <div className="flex items-center gap-0.5 shrink-0">
              <button onClick={() => zoom(-1)}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-white/45 hover:text-white/80 hover:bg-white/8 transition-colors">
                <ZoomOut size={14} />
              </button>
              <span className="text-[11px] text-white/35 w-10 text-center tabular-nums select-none">
                {Math.round(scale * 100)}%
              </span>
              <button onClick={() => zoom(1)}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-white/45 hover:text-white/80 hover:bg-white/8 transition-colors">
                <ZoomIn size={14} />
              </button>
              {/* Fit button */}
              <button
                onClick={() => setScale(fitScale)}
                title="Fit to page"
                className="w-7 h-7 flex items-center justify-center rounded-lg text-white/35 hover:text-white/70 hover:bg-white/8 transition-colors ml-0.5">
                <Maximize2 size={13} />
              </button>
              <div className="w-px h-4 bg-white/10 mx-1.5" />
              <button onClick={onClose}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors">
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Row 2: mode toggle + tier badge */}
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5 p-0.5 rounded-xl bg-white/[0.05] border border-white/[0.07]">
              <button
                onClick={() => switchMode('text')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-xs font-medium transition-all ${
                  mode === 'text' ? 'bg-violet-600 text-white' : 'text-white/45 hover:text-white/70'
                }`}>
                <MousePointer size={11} /> Select Text
              </button>
              <button
                onClick={() => switchMode('region')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-xs font-medium transition-all ${
                  mode === 'region' ? 'bg-violet-600 text-white' : 'text-white/45 hover:text-white/70'
                }`}>
                <Crop size={11} /> Select Region
              </button>
            </div>
            <span className={`ml-auto text-[10px] px-2 py-0.5 rounded-full border shrink-0 ${
              pageLimit === Infinity
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/25'
            }`}>
              {tier} · {pageLimit === Infinity ? 'unlimited' : `${pageLimit} page${pageLimit !== 1 ? 's' : ''}`}
            </span>
          </div>
        </div>

        {/* ── PDF viewport ────────────────────────────────────────────────────── */}
        <div ref={scrollRef}
          className="flex-1 overflow-auto bg-[#1a1a1a] flex justify-center py-6 px-6 min-h-0">
          {loading && (
            <div className="flex items-center gap-2 text-white/35 text-sm self-center">
              <Loader2 size={16} className="animate-spin" /> Loading PDF…
            </div>
          )}
          {error && <div className="text-red-400 text-sm self-center">{error}</div>}
          {!loading && !error && (
            <div className="relative inline-block select-none"
              style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.06)' }}>
              {/* Canvas — hi-DPI physical size, CSS-scaled display */}
              <canvas ref={canvasRef} style={{ display: 'block' }} />

              {/* Text layer — CSS-scale positioned spans for native selection */}
              <div
                ref={textLayerRef}
                className="pdf-tl"
                style={{ pointerEvents: mode === 'text' ? 'auto' : 'none' }}
                onMouseUp={() => {
                  const sel = window.getSelection()?.toString().trim();
                  if (sel) setSelectedText(sel);
                }}
              />

              {/* Region overlay */}
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
                  {!selRect && (
                    <div className="absolute inset-0 flex items-end justify-center pb-8 pointer-events-none">
                      <span className="bg-black/70 text-white/50 text-xs px-3 py-1.5 rounded-full border border-white/10">
                        Drag to select a region
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Text-mode idle hint */}
              {mode === 'text' && !selectedText && (
                <div className="absolute inset-0 flex items-end justify-center pb-8 pointer-events-none">
                  <span className="bg-black/70 text-white/50 text-xs px-3 py-1.5 rounded-full border border-white/10">
                    Highlight text to ask AI about it
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Page navigation ─────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-white/[0.05] bg-[#0f0f0f] shrink-0">
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage <= 1}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-white/35
                       hover:text-white/65 disabled:opacity-20 hover:bg-white/5 transition-colors">
            <ChevronLeft size={15} />
          </button>
          <div className="text-center">
            <span className="text-xs text-white/35">Page {currentPage} / {effectiveMax || '…'}</span>
            {numPages > pageLimit && (
              <span className="ml-2 text-[10px] text-amber-400/50">· {numPages - pageLimit} locked</span>
            )}
          </div>
          <button onClick={() => setCurrentPage(p => Math.min(effectiveMax, p + 1))}
            disabled={currentPage >= effectiveMax || effectiveMax === 0}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-white/35
                       hover:text-white/65 disabled:opacity-20 hover:bg-white/5 transition-colors">
            <ChevronRight size={15} />
          </button>
        </div>

        {/* ── Action panel ────────────────────────────────────────────────────── */}
        {hasSelection ? (
          <div className="border-t border-white/[0.07] bg-[#0f0f0f] shrink-0 flex flex-col gap-3 px-4 py-4">
            {/* Selection preview */}
            <div className="flex items-center gap-2 bg-violet-500/10 border border-violet-500/20 rounded-xl px-3 py-2">
              {selectedText ? (
                <>
                  <Sparkles size={12} className="text-violet-400 shrink-0" />
                  <span className="text-xs text-violet-300/80 flex-1 truncate">
                    "{selectedText.length > 100 ? selectedText.slice(0, 100) + '…' : selectedText}"
                  </span>
                </>
              ) : regionUrl ? (
                <>
                  <Crop size={12} className="text-violet-400 shrink-0" />
                  <img src={regionUrl} alt="" className="h-8 object-contain rounded border border-violet-500/25 bg-white/5 shrink-0" />
                  <span className="text-xs text-violet-300/60 flex-1">Region captured</span>
                </>
              ) : null}
              <button onClick={clearSelection} className="text-white/25 hover:text-white/55 transition-colors ml-auto shrink-0">
                <X size={13} />
              </button>
            </div>

            {/* Quick actions */}
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => fire('Explain this to me in simple terms')}
                className="flex flex-col items-center gap-1.5 px-2 py-3 rounded-xl
                           bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors">
                <Lightbulb size={15} />
                Explain
              </button>
              <button
                onClick={() => fire('Summarize this concisely')}
                className="flex flex-col items-center gap-1.5 px-2 py-3 rounded-xl
                           bg-white/[0.07] hover:bg-white/[0.12] border border-white/[0.09]
                           text-white/70 hover:text-white text-xs font-medium transition-colors">
                <AlignLeft size={15} />
                Summarize
              </button>
              <button
                onClick={() => fire('What are the key points or takeaways from this?')}
                className="flex flex-col items-center gap-1.5 px-2 py-3 rounded-xl
                           bg-white/[0.07] hover:bg-white/[0.12] border border-white/[0.09]
                           text-white/70 hover:text-white text-xs font-medium transition-colors">
                <ListChecks size={15} />
                Key points
              </button>
            </div>

            {/* Custom question */}
            {!showCustom ? (
              <button
                onClick={() => { setShowCustom(true); setTimeout(() => inputRef.current?.focus(), 50); }}
                className="flex items-center justify-center gap-1.5 py-2 rounded-xl
                           border border-white/[0.09] text-white/40 hover:text-white/65
                           text-xs transition-colors hover:bg-white/5">
                <MessageSquare size={12} /> Ask your own question…
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
        ) : (
          /* No selection — idle hint */
          <div className="border-t border-white/[0.07] bg-[#0f0f0f] shrink-0 px-4 py-4">
            <div className="flex items-center gap-4 rounded-xl bg-white/[0.04] border border-white/[0.06] px-4 py-3">
              {mode === 'text' ? (
                <>
                  <MousePointer size={16} className="text-violet-400 shrink-0" />
                  <div>
                    <p className="text-white/70 text-xs font-medium">Select any text</p>
                    <p className="text-white/30 text-[11px] mt-0.5">Highlight words or paragraphs — then Explain, Summarize or ask anything</p>
                  </div>
                </>
              ) : (
                <>
                  <Crop size={16} className="text-violet-400 shrink-0" />
                  <div>
                    <p className="text-white/70 text-xs font-medium">Draw a region</p>
                    <p className="text-white/30 text-[11px] mt-0.5">Drag to capture any diagram, chart, or image — then ask AI to explain it</p>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
