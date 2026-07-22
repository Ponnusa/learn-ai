'use client';
/**
 * PDFContextPicker — full-screen modal for selecting PDF pages to attach as
 * AI context. Left: thumbnail strip (click to select). Right: continuous
 * canvas view (hover to reveal per-page add/remove button). Both panels stay
 * in sync via shared `selected` state.
 */
import { useState, useRef, useEffect } from 'react';
import { X, Loader2, Scissors, Check, FileImage } from 'lucide-react';

const PDFJS_URL  = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const THUMB_SCALE = 0.22;
const PAGE_SCALE  = 1.3;

declare global { interface Window { pdfjsLib: any } }

export interface PDFContextPickerProps {
  file:      File;
  initial?:  number[];
  maxPages?: number;
  onClose:   () => void;
  onAttach:  (pageNums: number[]) => void;
}

export function PDFContextPicker({
  file, initial = [], maxPages = 3, onClose, onAttach,
}: PDFContextPickerProps) {
  const [numPages,  setNumPages]  = useState(0);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [loadError, setLoadError] = useState('');
  const [selected,  setSelected]  = useState<number[]>(initial);
  const [hovered,   setHovered]   = useState<number | null>(null);

  const pdfDocRef    = useRef<any>(null);
  const thumbRefs    = useRef<(HTMLCanvasElement | null)[]>([]);
  const pageCanvases = useRef<(HTMLCanvasElement | null)[]>([]);
  const pageContainers = useRef<(HTMLDivElement | null)[]>([]);

  // ── Load PDF.js + document ──────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        if (!window.pdfjsLib) {
          await new Promise<void>((resolve, reject) => {
            const s = document.createElement('script');
            s.src     = PDFJS_URL;
            s.onload  = () => resolve();
            s.onerror = () => reject(new Error('Failed to load PDF.js'));
            document.head.appendChild(s);
          });
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_URL;
        }
        const doc = await window.pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
        if (cancelled) return;
        pdfDocRef.current = doc;
        setNumPages(doc.numPages);
        setLoadState('ready');
      } catch (e: any) {
        if (!cancelled) { setLoadError(e.message || 'Failed to load PDF'); setLoadState('error'); }
      }
    }
    init();
    return () => { cancelled = true; };
  }, [file]);

  // ── Render thumbnails + full pages progressively ────────────────────────────
  useEffect(() => {
    if (!pdfDocRef.current || numPages === 0) return;
    let cancelled = false;
    (async () => {
      for (let i = 0; i < numPages; i++) {
        if (cancelled) break;
        try {
          const page = await pdfDocRef.current.getPage(i + 1);
          const dpr  = window.devicePixelRatio || 1;

          // Thumbnail
          const thumb = thumbRefs.current[i];
          if (thumb && !cancelled) {
            const tvBase = page.getViewport({ scale: THUMB_SCALE });
            const tvHi   = page.getViewport({ scale: THUMB_SCALE * dpr });
            thumb.width = tvHi.width; thumb.height = tvHi.height;
            thumb.style.width = `${tvBase.width}px`; thumb.style.height = `${tvBase.height}px`;
            await page.render({ canvasContext: thumb.getContext('2d')!, viewport: tvHi }).promise;
          }

          // Full-size page
          const canvas = pageCanvases.current[i];
          if (canvas && !cancelled) {
            const pvBase = page.getViewport({ scale: PAGE_SCALE });
            const pvHi   = page.getViewport({ scale: PAGE_SCALE * dpr });
            canvas.width = pvHi.width; canvas.height = pvHi.height;
            canvas.style.width = `${pvBase.width}px`; canvas.style.height = `${pvBase.height}px`;
            await page.render({ canvasContext: canvas.getContext('2d')!, viewport: pvHi }).promise;
          }
        } catch { /* ignore cancelled renders */ }
      }
    })();
    return () => { cancelled = true; };
  }, [numPages]);

  // ── Helpers ─────────────────────────────────────────────────────────────────
  function toggle(n: number) {
    setSelected(prev =>
      prev.includes(n)
        ? prev.filter(p => p !== n)
        : prev.length < maxPages ? [...prev, n] : prev,
    );
  }

  function scrollToPage(n: number) {
    pageContainers.current[n - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const sorted = selected.slice().sort((a, b) => a - b);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'rgba(0,0,0,0.92)' }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-white/10 bg-[#111] shrink-0">
        <Scissors size={13} className="text-violet-400 shrink-0" />
        <span className="text-white/70 text-sm font-medium">Select pages as context</span>
        {selected.length > 0 && (
          <span className="text-[11px] text-violet-400 bg-violet-500/15 px-2 py-0.5 rounded-full font-medium">
            {selected.length} / {maxPages}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {selected.length > 0 && (
            <button
              onClick={() => onAttach(sorted)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500
                         text-white text-xs font-semibold transition-colors shadow"
            >
              <FileImage size={12} />
              Attach {selected.length} page{selected.length > 1 ? 's' : ''}
            </button>
          )}
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-white/40 hover:text-white/80 hover:bg-white/8 transition-colors">
            <X size={15} />
          </button>
        </div>
      </div>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      {loadState === 'loading' && (
        <div className="flex-1 flex items-center justify-center gap-2 text-white/35 text-sm">
          <Loader2 size={16} className="animate-spin" /> Loading PDF…
        </div>
      )}
      {loadState === 'error' && (
        <div className="flex-1 flex items-center justify-center text-red-400 text-sm">{loadError}</div>
      )}

      {loadState === 'ready' && (
        <div className="flex flex-1 overflow-hidden">

          {/* Left: thumbnail strip */}
          <div className="w-[108px] shrink-0 overflow-y-auto bg-[#0d0d0d] border-r border-white/8">
            <div className="sticky top-0 z-10 px-2 pt-2 pb-1.5 bg-[#0d0d0d] border-b border-white/6">
              <p className="text-[9px] text-white/30 text-center leading-tight">
                Click to select
              </p>
            </div>
            <div className="flex flex-col items-center gap-2 py-3 px-2">
              {Array.from({ length: numPages }, (_, i) => {
                const n   = i + 1;
                const sel = selected.includes(n);
                const maxed = !sel && selected.length >= maxPages;
                return (
                  <button
                    key={i}
                    onClick={() => { toggle(n); scrollToPage(n); }}
                    title={sel ? `Deselect p.${n}` : maxed ? `Max ${maxPages} pages` : `Select p.${n}`}
                    className={[
                      'relative w-full rounded overflow-hidden border-2 transition-all shrink-0',
                      sel   ? 'border-violet-400 shadow-[0_0_0_2px_rgba(139,92,246,0.22)]'
                      : maxed ? 'border-white/5 opacity-25 cursor-not-allowed'
                      :         'border-white/10 hover:border-violet-400/50 cursor-pointer',
                    ].join(' ')}
                  >
                    <canvas
                      ref={el => { thumbRefs.current[i] = el; }}
                      style={{ display: 'block', width: '100%', height: 'auto' }}
                    />
                    {sel && (
                      <div className="absolute top-1 right-1 w-4 h-4 rounded-full bg-violet-500
                                      flex items-center justify-center shadow">
                        <Check size={8} className="text-white" strokeWidth={3} />
                      </div>
                    )}
                    <div className="absolute bottom-0 inset-x-0 text-[9px] text-center
                                    text-white/45 bg-black/55 py-0.5 leading-none">
                      {n}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: continuous full-page view */}
          <div className="flex-1 overflow-y-auto bg-[#1c1c1c] py-5">
            <div className="flex flex-col items-center gap-5">
              {Array.from({ length: numPages }, (_, i) => {
                const n     = i + 1;
                const sel   = selected.includes(n);
                const maxed = !sel && selected.length >= maxPages;
                return (
                  <div
                    key={i}
                    ref={el => { pageContainers.current[i] = el; }}
                    className="relative inline-block"
                    style={{
                      outline: sel
                        ? '2.5px solid rgb(139 92 246)'
                        : '1px solid rgba(255,255,255,0.05)',
                      boxShadow: sel
                        ? '0 0 0 4px rgba(139,92,246,0.15), 0 4px 24px rgba(0,0,0,0.5)'
                        : '0 2px 16px rgba(0,0,0,0.5)',
                      borderRadius: 2,
                    }}
                    onMouseEnter={() => setHovered(n)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <canvas
                      ref={el => { pageCanvases.current[i] = el; }}
                      style={{ display: 'block' }}
                    />

                    {/* Page number */}
                    <div className="absolute bottom-2 right-3 text-[10px] text-white/20 pointer-events-none select-none">
                      {n} / {numPages}
                    </div>

                    {/* Hover / selected action button */}
                    {(hovered === n || sel) && (
                      <button
                        onClick={() => toggle(n)}
                        disabled={maxed}
                        className={[
                          'absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1.5',
                          'rounded-lg text-[11px] font-semibold transition-all shadow-lg',
                          sel
                            ? 'bg-violet-500 text-white hover:bg-red-500/90'
                            : maxed
                              ? 'bg-black/60 text-white/30 cursor-not-allowed border border-white/8'
                              : 'bg-black/70 text-white hover:bg-violet-600 backdrop-blur-sm border border-white/15',
                        ].join(' ')}
                      >
                        {sel
                          ? <><Check size={10} strokeWidth={3} /> Added — click to remove</>
                          : maxed
                            ? <>Max {maxPages} pages</>
                            : <>+ Add page {n}</>}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
