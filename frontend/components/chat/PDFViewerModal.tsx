'use client';
import { useState, useRef, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import {
  X, ZoomIn, ZoomOut, MousePointer, Crop,
  ChevronLeft, ChevronRight, Send,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

// ── Worker (CDN — no webpack config needed) ──────────────────────────────────
pdfjs.GlobalWorkerOptions.workerSrc =
  `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// ── Tier page limits ──────────────────────────────────────────────────────────
const PAGE_LIMITS: Record<string, number> = {
  anonymous: 2,
  free:      3,
  learner:   10,
  pro:       Infinity,
};

type SelectionMode = 'text' | 'region';

interface SelectionRect {
  x: number; y: number; width: number; height: number;
}

interface PDFViewerModalProps {
  file: File;
  onClose: () => void;
  /** Called when user clicks "Ask". Text or imageDataUrl is the selection context. */
  onAsk: (question: string, context: { text?: string; imageDataUrl?: string }) => void;
}

export function PDFViewerModal({ file, onClose, onAsk }: PDFViewerModalProps) {
  const { user } = useSessionStore();
  const tier      = user?.tier ?? 'anonymous';
  const pageLimit = PAGE_LIMITS[tier] ?? 2;

  const [numPages,      setNumPages]      = useState(0);
  const [currentPage,   setCurrentPage]   = useState(1);
  const [scale,         setScale]         = useState(0.5);
  const [mode,          setMode]          = useState<SelectionMode>('text');
  const [selectedText,  setSelectedText]  = useState('');
  const [regionDataUrl, setRegionDataUrl] = useState<string | null>(null);
  const [question,      setQuestion]      = useState('');

  // Region-selection drawing state
  const [drawing,  setDrawing]  = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [selRect,  setSelRect]  = useState<SelectionRect | null>(null);

  const pageContainerRef = useRef<HTMLDivElement>(null);

  // ── Text selection capture ──────────────────────────────────────────────────
  useEffect(() => {
    if (mode !== 'text') return;
    const capture = () => {
      const sel = window.getSelection()?.toString().trim();
      if (sel) setSelectedText(sel);
    };
    document.addEventListener('mouseup', capture);
    return () => document.removeEventListener('mouseup', capture);
  }, [mode]);

  // ── Switch mode — clear opposite selection ──────────────────────────────────
  function switchMode(m: SelectionMode) {
    setMode(m);
    if (m === 'text')   { setRegionDataUrl(null); setSelRect(null); }
    if (m === 'region') { setSelectedText(''); }
  }

  // ── Region drawing mouse handlers ───────────────────────────────────────────
  function onOverlayMouseDown(e: React.MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    setStartPos({ x: e.clientX - r.left, y: e.clientY - r.top });
    setDrawing(true);
    setSelRect(null);
    setRegionDataUrl(null);
  }

  function onOverlayMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!drawing || !startPos) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    setSelRect({
      x:      Math.min(startPos.x, x),
      y:      Math.min(startPos.y, y),
      width:  Math.abs(x - startPos.x),
      height: Math.abs(y - startPos.y),
    });
  }

  function onOverlayMouseUp() {
    setDrawing(false);
    if (selRect && selRect.width > 10 && selRect.height > 10) {
      extractRegion(selRect);
    }
  }

  // ── Canvas region extraction ─────────────────────────────────────────────────
  function extractRegion(rect: SelectionRect) {
    const canvas = pageContainerRef.current?.querySelector('canvas');
    if (!canvas) return;

    // Map CSS-pixel coords to canvas pixel coords (accounts for device pixel ratio)
    const scaleX = canvas.width  / canvas.offsetWidth;
    const scaleY = canvas.height / canvas.offsetHeight;

    const offscreen = document.createElement('canvas');
    offscreen.width  = Math.round(rect.width  * scaleX);
    offscreen.height = Math.round(rect.height * scaleY);

    const ctx = offscreen.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(
      canvas,
      Math.round(rect.x * scaleX),
      Math.round(rect.y * scaleY),
      offscreen.width,
      offscreen.height,
      0, 0,
      offscreen.width,
      offscreen.height,
    );
    setRegionDataUrl(offscreen.toDataURL('image/png'));
  }

  // ── Ask handler ──────────────────────────────────────────────────────────────
  function handleAsk() {
    if (!question.trim()) return;
    if (mode === 'text') {
      onAsk(question.trim(), { text: selectedText || undefined });
    } else {
      onAsk(question.trim(), { imageDataUrl: regionDataUrl ?? undefined });
    }
  }

  const effectiveMax = numPages > 0 ? Math.min(numPages, pageLimit) : pageLimit;
  const hasSelection = mode === 'text' ? !!selectedText : !!regionDataUrl;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-[#111] border border-white/10 rounded-2xl w-full max-w-4xl h-[92vh] flex flex-col overflow-hidden shadow-2xl">

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0">
          {/* Left: filename + tier badge */}
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-white/90 font-medium text-sm truncate max-w-xs">{file.name}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${
              pageLimit === Infinity
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
            }`}>
              {tier} · {pageLimit === Infinity ? 'unlimited pages' : `${pageLimit} page${pageLimit !== 1 ? 's' : ''} max`}
            </span>
          </div>

          {/* Right: mode + zoom + close */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Mode toggle */}
            <button
              onClick={() => switchMode('text')}
              title="Select text"
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${
                mode === 'text'
                  ? 'bg-purple-600/30 border-purple-500/50 text-purple-300'
                  : 'bg-white/5 border-white/10 text-white/45 hover:text-white/70'
              }`}
            >
              <MousePointer size={12} /> Text
            </button>
            <button
              onClick={() => switchMode('region')}
              title="Select region"
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${
                mode === 'region'
                  ? 'bg-purple-600/30 border-purple-500/50 text-purple-300'
                  : 'bg-white/5 border-white/10 text-white/45 hover:text-white/70'
              }`}
            >
              <Crop size={12} /> Region
            </button>

            {/* Zoom controls */}
            <div className="flex items-center gap-0.5 ml-2">
              <button
                onClick={() => setScale(s => parseFloat(Math.max(0.25, s - 0.1).toFixed(1)))}
                className="text-white/45 hover:text-white/80 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                title="Zoom out"
              >
                <ZoomOut size={15} />
              </button>
              <span className="text-xs text-white/35 w-10 text-center tabular-nums">
                {Math.round(scale * 100)}%
              </span>
              <button
                onClick={() => setScale(s => parseFloat(Math.min(2.0, s + 0.1).toFixed(1)))}
                className="text-white/45 hover:text-white/80 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                title="Zoom in"
              >
                <ZoomIn size={15} />
              </button>
            </div>

            {/* Close */}
            <button
              onClick={onClose}
              className="text-white/45 hover:text-white/80 p-1.5 rounded-lg hover:bg-white/5 transition-colors ml-1"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── PDF canvas area ─────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-auto bg-[#1c1c1c] flex justify-center py-4 px-4">
          <div
            ref={pageContainerRef}
            className="relative inline-block shadow-2xl shadow-black/50"
          >
            <Document
              file={file}
              onLoadSuccess={({ numPages }) => setNumPages(numPages)}
              loading={
                <div className="flex items-center justify-center w-64 h-80 text-white/40 text-sm">
                  Loading PDF…
                </div>
              }
              error={
                <div className="flex items-center justify-center w-64 h-80 text-red-400 text-sm">
                  Failed to load PDF
                </div>
              }
            >
              <Page
                pageNumber={Math.min(currentPage, effectiveMax)}
                scale={scale}
                renderTextLayer={mode === 'text'}
                renderAnnotationLayer={false}
              />
            </Document>

            {/* Region selection overlay (only in region mode) */}
            {mode === 'region' && (
              <div
                className="absolute inset-0"
                style={{ cursor: 'crosshair', userSelect: 'none' }}
                onMouseDown={onOverlayMouseDown}
                onMouseMove={onOverlayMouseMove}
                onMouseUp={onOverlayMouseUp}
                onMouseLeave={onOverlayMouseUp}
              >
                {selRect && (
                  <div
                    className="absolute border-2 border-purple-400 bg-purple-400/10 rounded-sm pointer-events-none"
                    style={{
                      left:   selRect.x,
                      top:    selRect.y,
                      width:  selRect.width,
                      height: selRect.height,
                    }}
                  />
                )}
                {!selRect && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <span className="bg-black/60 text-white/50 text-xs px-3 py-1.5 rounded-full border border-white/10">
                      Drag to select a region
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── Page navigation ─────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-white/[0.06] bg-[#111] shrink-0">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="text-white/40 hover:text-white/70 disabled:opacity-25 p-1 rounded transition-colors"
          >
            <ChevronLeft size={16} />
          </button>

          <div className="text-center">
            <span className="text-xs text-white/40">
              Page {currentPage} of {effectiveMax > 0 ? effectiveMax : '…'}
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
            className="text-white/40 hover:text-white/70 disabled:opacity-25 p-1 rounded transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* ── Selection preview strip ─────────────────────────────────────────── */}
        {hasSelection && (
          <div className="px-4 py-2 bg-purple-950/40 border-t border-purple-500/20 flex items-center gap-3 shrink-0">
            <span className="text-[10px] text-purple-400/70 uppercase tracking-wider shrink-0">
              Selected:
            </span>
            {selectedText && (
              <span className="text-xs text-purple-300/80 truncate">
                "{selectedText.length > 120 ? selectedText.slice(0, 120) + '…' : selectedText}"
              </span>
            )}
            {regionDataUrl && (
              <div className="flex items-center gap-2">
                <img
                  src={regionDataUrl}
                  alt="Selected region"
                  className="h-9 object-contain rounded border border-purple-500/30 bg-white/5"
                />
                <span className="text-xs text-purple-300/60">Region captured</span>
              </div>
            )}
            <button
              onClick={() => { setSelectedText(''); setRegionDataUrl(null); setSelRect(null); }}
              className="ml-auto text-white/30 hover:text-white/60 shrink-0"
              title="Clear selection"
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
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(); }
            }}
            placeholder={
              mode === 'text'
                ? 'Select text in the PDF, then ask a question about it…'
                : 'Drag to select a region, then ask a question about it…'
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
            <Send size={14} />
            Ask
          </button>
        </div>

      </div>
    </div>
  );
}
