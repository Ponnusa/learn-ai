'use client';
/**
 * ContinuousSnipModal — renders all PDF pages in a continuous vertical scroll
 * for Studio chat PDF clip. Drag on any page to snip a region.
 *
 * Drag is tracked by attaching mousemove/mouseup to document at mousedown time
 * (classic closure pattern), so events are never lost when the cursor exits the
 * page overlay or the user scrolls mid-drag.
 */
import { useState, useRef, useEffect } from 'react';
import { X, Loader2, Scissors } from 'lucide-react';

const PDFJS_URL  = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
const WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const RENDER_SCALE = 1.4;

declare global { interface Window { pdfjsLib: any } }

interface Rect { x: number; y: number; w: number; h: number }

export interface SnipAction {
  label:    string;
  primary?: boolean;
  icon:     React.ComponentType<{ size?: number; className?: string }>;
  onClick:  (imageDataUrl: string) => void;
}

interface Props {
  file:    File;
  onClose: () => void;
  actions: SnipAction[];
}

interface SelInfo { pageIdx: number; rect: Rect }
interface Captured { url: string; menuX: number; menuY: number }

export function ContinuousSnipModal({ file, onClose, actions }: Props) {
  const [pdfDoc,    setPdfDoc]    = useState<any>(null);
  const [numPages,  setNumPages]  = useState(0);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [loadError, setLoadError] = useState('');

  const [selInfo,  setSelInfo]  = useState<SelInfo | null>(null);
  const [captured, setCaptured] = useState<Captured | null>(null);

  const canvasRefs  = useRef<(HTMLCanvasElement | null)[]>([]);
  const dragCleanup = useRef<(() => void) | null>(null);

  // ── Load PDF.js + open document ─────────────────────────────────────────────
  useEffect(() => {
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

  // ── Render all pages once doc is loaded ─────────────────────────────────────
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
          canvas.width        = hi.width;
          canvas.height       = hi.height;
          canvas.style.width  = `${base.width}px`;
          canvas.style.height = `${base.height}px`;
          await page.render({ canvasContext: canvas.getContext('2d')!, viewport: hi }).promise;
        } catch { /* ignore */ }
      }
    })();
    return () => { cancelled = true; };
  }, [pdfDoc, numPages, loadState]);

  // ── Unmount: clean up any in-progress drag listeners ────────────────────────
  useEffect(() => () => { dragCleanup.current?.(); }, []);

  // ── Drag: classic closure-based approach (no stale state issues) ─────────────
  function startDrag(pageIdx: number, e: React.MouseEvent<HTMLDivElement>) {
    e.preventDefault();

    // Single click on captured state → clear
    if (captured) { setCaptured(null); setSelInfo(null); return; }

    const canvas = canvasRefs.current[pageIdx];
    if (!canvas) return;

    const clientStartX = e.clientX;
    const clientStartY = e.clientY;

    // Compute selection rect in canvas-local coords (fresh canvas position each call)
    function getRect(clientX: number, clientY: number): Rect {
      const r  = canvas!.getBoundingClientRect();
      const sx = clientStartX - r.left;
      const sy = clientStartY - r.top;
      const ex = clientX - r.left;
      const ey = clientY - r.top;
      return {
        x: Math.min(sx, ex), y: Math.min(sy, ey),
        w: Math.abs(ex - sx), h: Math.abs(ey - sy),
      };
    }

    setCaptured(null);
    setSelInfo({ pageIdx, rect: { x: clientStartX - canvas.getBoundingClientRect().left, y: clientStartY - canvas.getBoundingClientRect().top, w: 0, h: 0 } });

    function onMove(me: MouseEvent) {
      setSelInfo({ pageIdx, rect: getRect(me.clientX, me.clientY) });
    }

    function onUp(me: MouseEvent) {
      cleanup();
      const rect = getRect(me.clientX, me.clientY);
      if (rect.w < 10 || rect.h < 10) { setSelInfo(null); return; }

      setSelInfo({ pageIdx, rect });

      // Extract from canvas
      const scaleX = canvas!.width  / canvas!.offsetWidth;
      const scaleY = canvas!.height / canvas!.offsetHeight;
      const off    = document.createElement('canvas');
      off.width    = Math.round(rect.w * scaleX);
      off.height   = Math.round(rect.h * scaleY);
      const ctx    = off.getContext('2d');
      if (!ctx || off.width < 1 || off.height < 1) { setSelInfo(null); return; }
      ctx.drawImage(
        canvas!,
        Math.round(rect.x * scaleX), Math.round(rect.y * scaleY),
        off.width, off.height,
        0, 0, off.width, off.height,
      );
      const url = off.toDataURL('image/png');

      // Fixed viewport position for the context menu
      const cr = canvas!.getBoundingClientRect();
      setCaptured({ url, menuX: cr.left + rect.x + rect.w / 2, menuY: cr.top + rect.y + rect.h + 12 });
    }

    function cleanup() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onUp);
      dragCleanup.current = null;
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup',   onUp);
    dragCleanup.current = cleanup;
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  const menuH = actions.length * 44 + 32;

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'rgba(0,0,0,0.88)' }}>
      <style>{`
        @keyframes snipIn { from { opacity:0; transform:scale(0.93) } to { opacity:1; transform:scale(1) } }
      `}</style>

      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-white/10 bg-[#111] shrink-0">
        <Scissors size={13} className="text-violet-400 shrink-0" />
        <span className="text-white/65 text-xs font-medium">Drag to clip any region</span>
        <span className="text-white/25 text-[11px]">· scroll to read · click to clear</span>
        <button onClick={onClose}
          className="ml-auto w-7 h-7 flex items-center justify-center rounded-lg
                     text-white/35 hover:text-white/75 hover:bg-white/8 transition-colors shrink-0">
          <X size={15} />
        </button>
      </div>

      {/* Pages */}
      <div className="flex-1 overflow-y-auto bg-[#1c1c1c] py-5"
        onClick={() => { if (captured) { setCaptured(null); setSelInfo(null); } }}>

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
              <div key={i} className="relative inline-block"
                style={{ boxShadow: '0 2px 16px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.05)', userSelect: 'none' }}>

                <canvas ref={el => { canvasRefs.current[i] = el; }} style={{ display: 'block' }} />

                {/* Overlay: only mousedown here; move+up go on document */}
                <div
                  className="absolute inset-0"
                  style={{ cursor: captured ? 'default' : 'crosshair' }}
                  onMouseDown={e => startDrag(i, e)}
                >
                  {/* Live selection */}
                  {!captured && selInfo?.pageIdx === i && selInfo.rect.w > 2 && (
                    <div className="absolute border-2 border-violet-400 bg-violet-500/10 pointer-events-none rounded-sm"
                      style={{ left: selInfo.rect.x, top: selInfo.rect.y,
                               width: selInfo.rect.w, height: selInfo.rect.h }} />
                  )}
                  {/* Captured highlight */}
                  {captured && selInfo?.pageIdx === i && (
                    <>
                      <div className="absolute inset-0 bg-black/45 pointer-events-none" />
                      <div className="absolute border-2 border-violet-400 pointer-events-none rounded-sm"
                        style={{ left: selInfo.rect.x, top: selInfo.rect.y,
                                 width: selInfo.rect.w, height: selInfo.rect.h,
                                 outline: '9999px solid rgba(0,0,0,0.45)' }} />
                    </>
                  )}
                </div>

                <div className="absolute bottom-1.5 right-2 text-[10px] text-white/20 pointer-events-none">
                  {i + 1} / {numPages}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Context menu */}
      {captured && (() => {
        const W  = 218;
        const vw = window.innerWidth, vh = window.innerHeight;
        const cx = Math.max(8, Math.min(vw - W - 8, captured.menuX - W / 2));
        const cy = captured.menuY + menuH < vh
          ? captured.menuY
          : captured.menuY - menuH - (selInfo?.rect.h ?? 0) - 24;
        return (
          <div
            className="fixed z-[60] bg-[#1c1c1e] border border-white/[0.13] rounded-2xl shadow-2xl overflow-hidden"
            style={{ left: cx, top: Math.max(8, Math.min(vh - menuH - 8, cy)), width: W,
                     animation: 'snipIn 0.12s ease' }}
            onMouseDown={e => e.stopPropagation()}
            onClick={e => e.stopPropagation()}
          >
            {actions.map((a, idx) => {
              const Icon = a.icon;
              return (
                <button key={idx} onClick={() => a.onClick(captured.url)}
                  className={a.primary
                    ? 'w-full flex items-center gap-2.5 px-4 py-3 text-sm font-semibold text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 transition-colors'
                    : 'w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium text-white/60 hover:text-white hover:bg-white/[0.07] transition-colors'
                  }>
                  <Icon size={a.primary ? 14 : 13} className="shrink-0" /> {a.label}
                </button>
              );
            })}
            <div className="h-px bg-white/[0.07]" />
            <button onClick={() => { setCaptured(null); setSelInfo(null); }}
              className="w-full flex items-center gap-2 px-4 py-1.5 text-[10px] text-white/25 hover:text-white/50 hover:bg-white/[0.04] transition-colors">
              <X size={10} className="shrink-0" /> Clear selection
            </button>
          </div>
        );
      })()}
    </div>
  );
}
