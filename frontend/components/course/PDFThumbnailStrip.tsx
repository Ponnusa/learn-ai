'use client';
import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { Loader2, Check } from 'lucide-react';

const PDFJS_URL  = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const THUMB_SCALE = 0.25;
const SEND_SCALE  = 1.8;  // resolution for images sent to GPT-4o

declare global { interface Window { pdfjsLib: any } }

export interface PDFThumbnailStripRef {
  renderPage: (pageNum: number) => Promise<string>; // returns data URL (JPEG)
}

interface Props {
  file:          File;
  selectedPages: number[];   // 1-indexed
  onTogglePage:  (n: number) => void;
  maxSelect?:    number;
}

export const PDFThumbnailStrip = forwardRef<PDFThumbnailStripRef, Props>(
  ({ file, selectedPages, onTogglePage, maxSelect = 3 }, ref) => {
    const [numPages,  setNumPages]  = useState(0);
    const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');

    const pdfDocRef  = useRef<any>(null);
    const canvasRefs = useRef<(HTMLCanvasElement | null)[]>([]);

    // Expose renderPage to parent via ref
    useImperativeHandle(ref, () => ({
      async renderPage(pageNum: number): Promise<string> {
        const doc = pdfDocRef.current;
        if (!doc) throw new Error('PDF not loaded');
        const page   = await doc.getPage(pageNum);
        const dpr    = window.devicePixelRatio || 1;
        const vp     = page.getViewport({ scale: SEND_SCALE * dpr });
        const canvas = document.createElement('canvas');
        canvas.width  = vp.width;
        canvas.height = vp.height;
        await page.render({ canvasContext: canvas.getContext('2d')!, viewport: vp }).promise;
        return canvas.toDataURL('image/jpeg', 0.88);
      },
    }));

    // Load PDF.js + document
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
          const data = await file.arrayBuffer();
          if (cancelled) return;
          const doc = await window.pdfjsLib.getDocument({ data }).promise;
          if (cancelled) return;
          pdfDocRef.current = doc;
          setNumPages(doc.numPages);
          setLoadState('ready');
        } catch {
          if (!cancelled) setLoadState('error');
        }
      }
      init();
      return () => { cancelled = true; };
    }, [file]);

    // Render thumbnails after numPages is set
    useEffect(() => {
      if (!pdfDocRef.current || numPages === 0) return;
      let cancelled = false;
      (async () => {
        for (let i = 0; i < numPages; i++) {
          const canvas = canvasRefs.current[i];
          if (!canvas || cancelled) break;
          try {
            const page  = await pdfDocRef.current.getPage(i + 1);
            const dpr   = window.devicePixelRatio || 1;
            const base  = page.getViewport({ scale: THUMB_SCALE });
            const hi    = page.getViewport({ scale: THUMB_SCALE * dpr });
            canvas.width        = hi.width;
            canvas.height       = hi.height;
            canvas.style.width  = `${base.width}px`;
            canvas.style.height = `${base.height}px`;
            await page.render({ canvasContext: canvas.getContext('2d')!, viewport: hi }).promise;
          } catch { /* ignore */ }
        }
      })();
      return () => { cancelled = true; };
    }, [numPages]);

    if (loadState === 'loading') return (
      <div className="flex items-center justify-center py-6">
        <Loader2 size={14} className="animate-spin text-white/25" />
      </div>
    );

    if (loadState === 'error') return (
      <div className="text-[10px] text-red-400/60 px-2 py-3 text-center">Failed</div>
    );

    return (
      <div className="flex flex-col items-center gap-2 py-3 px-1.5">
        {Array.from({ length: numPages }, (_, i) => {
          const pageNum  = i + 1;
          const selected = selectedPages.includes(pageNum);
          const maxed    = !selected && selectedPages.length >= maxSelect;
          return (
            <button
              key={i}
              type="button"
              onClick={() => !maxed && onTogglePage(pageNum)}
              title={
                selected ? `Deselect page ${pageNum}`
                : maxed  ? `Max ${maxSelect} pages selected`
                :          `Add page ${pageNum} as context`
              }
              className={[
                'relative rounded overflow-hidden border-2 transition-all shrink-0 w-[84px]',
                selected ? 'border-violet-400 shadow-[0_0_0_2px_rgba(139,92,246,0.25)]'
                : maxed  ? 'border-white/5 opacity-35 cursor-not-allowed'
                :          'border-white/10 hover:border-violet-400/50 cursor-pointer',
              ].join(' ')}
            >
              <canvas
                ref={el => { canvasRefs.current[i] = el; }}
                style={{ display: 'block', width: '100%', height: 'auto' }}
              />
              {selected && (
                <div className="absolute top-1 right-1 w-4 h-4 rounded-full bg-violet-500
                                flex items-center justify-center shadow">
                  <Check size={9} className="text-white" strokeWidth={3} />
                </div>
              )}
              <div className="absolute bottom-0 inset-x-0 text-center text-[9px]
                              text-white/50 bg-black/50 py-0.5 leading-none">
                {pageNum}
              </div>
            </button>
          );
        })}
      </div>
    );
  }
);

PDFThumbnailStrip.displayName = 'PDFThumbnailStrip';
