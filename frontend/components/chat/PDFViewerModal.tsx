'use client';
/**
 * PDFViewerModal
 *
 * Loads PDF.js v3 from CDN at runtime — zero webpack bundle, no build crashes.
 * Renders pages directly to a <canvas> for full pixel access.
 * Text mode: extracts text via getTextContent() shown as selectable HTML.
 * Region mode: draw selection rect over the canvas → extract via drawImage.
 */
import { useState, useRef, useEffect } from 'react';
import {
  X, ZoomIn, ZoomOut, MousePointer, Crop,
  ChevronLeft, ChevronRight, Send, Loader2,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

// PDF.js v3 — stable, CommonJS, widely tested. Loaded from CDN at runtime.
const PDFJS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

// Tier page limits (mirrors backend tier_config)
const PAGE_LIMITS: Record<string, number> = {
  anonymous: 2,
  free:      3,
  learner:   10,
  pro:       Infinity,
};

type Mode = 'text' | 'region';
interface Rect { x: number; y: number; w: number; h: number }

// Augment Window so TypeScript knows about the runtime global
declare global {
  interface Window { pdfjsLib: any }
}

interface PDFViewerModalProps {
  file: File;
  onClose: () => void;
  onAsk: (question: string, context: { text?: string; imageDataUrl?: string }) => void;
}

export function PDFViewerModal({ file, onClose, onAsk }: PDFViewerModalProps) {
  const { user } = useSessionStore();
  const tier      = user?.tier ?? 'anonymous';
  const pageLimit = PAGE_LIMITS[tier] ?? 2;

  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [pdfDoc,       setPdfDoc]       = useState<any>(null);
  const [numPages,     setNumPages]     = useState(0);
  const [currentPage,  setCurrentPage]  = useState(1);
  const [scale,        setScale]        = useState(0.5);
  const [mode,         setMode]         = useState<Mode>('text');
  const [pageText,     setPageText]     = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [regionUrl,    setRegionUrl]    = useState<string | null>(null);
  const [question,     setQuestion]     = useState('');
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState('');

  // Region-draw state
  const [drawing,  setDrawing]  = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [selRect,  setSelRect]  = useState<Rect | null>(null);

  const effectiveMax = numPages > 0 ? Math.min(numPages, pageLimit) : 0;

  // ── 1. Load PDF.js from CDN then open the file ───────────────────────────────
  useEffect(() => {
    async function loadLibAndFile() {
      try {
        if (!window.pdfjsLib) {
          await new Promise<void>((resolve, reject) => {
            const s = document.createElement('script');
            s.src = PDFJS_URL;
            s.onload  = () => resolve();
            s.onerror = () => reject(new Error('Failed to load PDF.js from CDN'));
            document.head.appendChild(s);
          });
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_URL;
        }

        const data = await file.arrayBuffer();
        const doc  = await window.pdfjsLib.getDocument({ data }).promise;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setLoading(false);
      } catch (e: any) {
        setError(e.message || 'Failed to load PDF');
        setLoading(false);
      }
    }
    loadLibAndFile();
  }, [file]);

  // ── 2. Render the current page ───────────────────────────────────────────────
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;
    let cancelled = false;

    async function renderPage() {
      try {
        const page     = await pdfDoc.getPage(currentPage);
        if (cancelled) return;

        const viewport = page.getViewport({ scale });
        const canvas   = canvasRef.current!;
        canvas.width   = viewport.width;
        canvas.height  = viewport.height;

        await page.render({
          canvasContext: canvas.getContext('2d')!,
          viewport,
        }).promise;

        // Extract text for the text panel
        const content = await page.getTextContent();
        if (!cancelled) {
          const text = content.items
            .map((item: any) => item.str)
            .filter((s: string) => s.trim())
            .join(' ');
          setPageText(text);
          // Clear previous selections when page/zoom changes
          setSelRect(null);
          setRegionUrl(null);
        }
      } catch {
        // Non-fatal — canvas stays blank
      }
    }

    renderPage();
    return () => { cancelled = true; };
  }, [pdfDoc, currentPage, scale]);

  // ── 3. Region selection mouse handlers ───────────────────────────────────────
  function onMouseDown(e: React.MouseEvent<HTMLDivElement>) {
    if (mode !== 'region') return;
    const r = e.currentTarget.getBoundingClientRect();
    setStartPos({ x: e.clientX - r.left, y: e.clientY - r.top });
    setDrawing(true);
    setSelRect(null);
    setRegionUrl(null);
  }

  function onMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!drawing || !startPos) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    setSelRect({
      x: Math.min(startPos.x, x),
      y: Math.min(startPos.y, y),
      w: Math.abs(x - startPos.x),
      h: Math.abs(y - startPos.y),
    });
  }

  function onMouseUp() {
    if (!drawing) return;
    setDrawing(false);
    if (selRect && selRect.w > 10 && selRect.h > 10) {
      extractRegion(selRect);
    }
  }

  function extractRegion(rect: Rect) {
    const canvas  = canvasRef.current;
    if (!canvas) return;
    // Canvas internal pixels may differ from CSS pixels (device pixel ratio)
    const scaleX  = canvas.width  / canvas.offsetWidth;
    const scaleY  = canvas.height / canvas.offsetHeight;
    const offscreen = document.createElement('canvas');
    offscreen.width  = Math.round(rect.w * scaleX);
    offscreen.height = Math.round(rect.h * scaleY);
    const ctx = offscreen.getContext('2d')!;
    ctx.drawImage(
      canvas,
      Math.round(rect.x * scaleX), Math.round(rect.y * scaleY),
      offscreen.width, offscreen.height,
      0, 0, offscreen.width, offscreen.height,
    );
    setRegionUrl(offscreen.toDataURL('image/png'));
  }

  // ── 4. Ask ───────────────────────────────────────────────────────────────────
  function handleAsk() {
    if (!question.trim()) return;
    if (mode === 'text') {
      const ctx = selectedText || pageText.slice(0, 2000) || undefined;
      onAsk(question.trim(), { text: ctx });
    } else {
      onAsk(question.trim(), { imageDataUrl: regionUrl ?? undefined });
    }
  }

  function switchMode(m: Mode) {
    setMode(m);
    if (m === 'text')   { setRegionUrl(null); setSelRect(null); }
    if (m === 'region') { setSelectedText(''); }
  }

  const hasSelection = mode === 'text' ? !!selectedText : !!regionUrl;

  // ────────────────────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-[#111] border border-white/10 rounded-2xl w-full max-w-4xl h-[92vh] flex flex-col overflow-hidden shadow-2xl">

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-white/90 font-medium text-sm truncate max-w-xs">{file.name}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${
              pageLimit === Infinity
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
            }`}>
              {tier} · {pageLimit === Infinity ? 'unlimited' : `${pageLimit} page${pageLimit !== 1 ? 's' : ''} max`}
            </span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {/* Mode buttons */}
            <button onClick={() => switchMode('text')}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${
                mode === 'text'
                  ? 'bg-purple-600/30 border-purple-500/50 text-purple-300'
                  : 'bg-white/5 border-white/10 text-white/45 hover:text-white/70'
              }`}>
              <MousePointer size={12} /> Select Text
            </button>
            <button onClick={() => switchMode('region')}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${
                mode === 'region'
                  ? 'bg-purple-600/30 border-purple-500/50 text-purple-300'
                  : 'bg-white/5 border-white/10 text-white/45 hover:text-white/70'
              }`}>
              <Crop size={12} /> Select Region
            </button>

            {/* Zoom */}
            <button onClick={() => setScale(s => parseFloat(Math.max(0.25, s - 0.1).toFixed(1)))}
              className="text-white/45 hover:text-white/80 p-1.5 rounded-lg hover:bg-white/5 transition-colors ml-1">
              <ZoomOut size={15} />
            </button>
            <span className="text-xs text-white/35 w-10 text-center tabular-nums">
              {Math.round(scale * 100)}%
            </span>
            <button onClick={() => setScale(s => parseFloat(Math.min(2.0, s + 0.1).toFixed(1)))}
              className="text-white/45 hover:text-white/80 p-1.5 rounded-lg hover:bg-white/5 transition-colors">
              <ZoomIn size={15} />
            </button>

            {/* Close */}
            <button onClick={onClose}
              className="text-white/45 hover:text-white/80 p-1.5 rounded-lg hover:bg-white/5 transition-colors ml-1">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── Canvas viewport ─────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-auto bg-[#1c1c1c] flex justify-center py-4 px-4">
          {loading && (
            <div className="flex items-center gap-2 text-white/40 text-sm self-center">
              <Loader2 size={16} className="animate-spin" /> Loading PDF…
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center text-red-400 text-sm self-center">
              {error}
            </div>
          )}
          {!loading && !error && (
            <div
              className="relative inline-block shadow-2xl shadow-black/60"
              style={{ cursor: mode === 'region' ? 'crosshair' : 'default', userSelect: mode === 'region' ? 'none' : 'auto' }}
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={onMouseUp}
              onMouseLeave={onMouseUp}
            >
              <canvas ref={canvasRef} />

              {/* Region selection rect overlay */}
              {mode === 'region' && selRect && (
                <div
                  className="absolute border-2 border-purple-400 bg-purple-400/10 rounded-sm pointer-events-none"
                  style={{ left: selRect.x, top: selRect.y, width: selRect.w, height: selRect.h }}
                />
              )}
              {mode === 'region' && !selRect && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <span className="bg-black/60 text-white/50 text-xs px-3 py-1.5 rounded-full border border-white/10">
                    Drag to select a region
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Page navigation ─────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-white/[0.06] bg-[#111] shrink-0">
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage <= 1}
            className="text-white/40 hover:text-white/70 disabled:opacity-25 p-1 rounded transition-colors">
            <ChevronLeft size={16} />
          </button>
          <div className="text-center">
            <span className="text-xs text-white/40">
              Page {currentPage} of {effectiveMax || '…'}
            </span>
            {numPages > pageLimit && (
              <span className="ml-2 text-[10px] text-amber-400/60">
                · {numPages - pageLimit} more page{numPages - pageLimit !== 1 ? 's' : ''} — upgrade to unlock
              </span>
            )}
          </div>
          <button
            onClick={() => setCurrentPage(p => Math.min(effectiveMax, p + 1))}
            disabled={currentPage >= effectiveMax || effectiveMax === 0}
            className="text-white/40 hover:text-white/70 disabled:opacity-25 p-1 rounded transition-colors">
            <ChevronRight size={16} />
          </button>
        </div>

        {/* ── Text panel (text mode only) ─────────────────────────────────────── */}
        {mode === 'text' && pageText && (
          <div className="px-4 py-2 border-t border-white/[0.06] bg-[#0f0f0f] shrink-0 max-h-32 overflow-y-auto">
            <p className="text-[10px] text-white/25 mb-1.5 uppercase tracking-wider">
              Page text — highlight to select:
            </p>
            <p
              className="text-xs text-white/55 leading-relaxed select-text"
              onMouseUp={() => {
                const sel = window.getSelection()?.toString().trim();
                if (sel) setSelectedText(sel);
              }}
            >
              {pageText}
            </p>
          </div>
        )}

        {/* ── Selection preview ───────────────────────────────────────────────── */}
        {hasSelection && (
          <div className="px-4 py-2 bg-purple-950/40 border-t border-purple-500/20 flex items-center gap-3 shrink-0">
            <span className="text-[10px] text-purple-400/70 uppercase tracking-wider shrink-0">
              Selected:
            </span>
            {selectedText && (
              <span className="text-xs text-purple-300/80 truncate">
                "{selectedText.length > 110 ? selectedText.slice(0, 110) + '…' : selectedText}"
              </span>
            )}
            {regionUrl && (
              <div className="flex items-center gap-2">
                <img src={regionUrl} alt="" className="h-9 object-contain rounded border border-purple-500/30 bg-white/5" />
                <span className="text-xs text-purple-300/60">Region captured</span>
              </div>
            )}
            <button
              onClick={() => { setSelectedText(''); setRegionUrl(null); setSelRect(null); }}
              className="ml-auto text-white/30 hover:text-white/60 transition-colors"
            >
              <X size={13} />
            </button>
          </div>
        )}

        {/* ── Ask footer ──────────────────────────────────────────────────────── */}
        <div className="px-4 py-3 border-t border-white/10 flex gap-2 bg-[#111] shrink-0">
          <textarea
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(); } }}
            placeholder={
              mode === 'text'
                ? 'Highlight text above, then type your question…'
                : 'Drag a region above, then type your question…'
            }
            rows={2}
            className="flex-1 bg-[#1e1e1e] border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-white/25 outline-none resize-none focus:border-purple-500/50 transition-colors leading-snug"
          />
          <button
            onClick={handleAsk}
            disabled={!question.trim()}
            className="self-end px-4 py-2.5 rounded-xl text-sm font-medium flex items-center gap-1.5 transition-all shrink-0
                       bg-purple-600 hover:bg-purple-500 text-white
                       disabled:opacity-35 disabled:cursor-not-allowed"
          >
            <Send size={14} /> Ask
          </button>
        </div>

      </div>
    </div>
  );
}
