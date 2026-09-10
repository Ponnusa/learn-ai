import { useRef, useState } from 'react';
import type { GenieStrings } from '../lib/i18n';

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface ClipCaptureProps {
  t: GenieStrings;
  /** Full-viewport screenshot from chrome.tabs.captureVisibleTab(), as a data URL. */
  dataUrl: string;
  onConfirm: (croppedDataUrl: string) => void;
  onCancel: () => void;
}

// Drag-select crop over a captured screenshot, mirroring the region-capture
// UX frontend/components/chat/PDFViewerModal.tsx already uses for PDFs
// (drag a rectangle -> crop to PNG -> sent as image_url/vision) — same
// pattern, just sourced from a live tab capture instead of a rendered PDF
// page, so it works on anything visible on screen, not just PDFs.
export function ClipCapture({ t, dataUrl, onConfirm, onCancel }: ClipCaptureProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef<{ x: number; y: number } | null>(null);
  const [rect, setRect] = useState<Rect | null>(null);

  function pos(e: React.MouseEvent) {
    const b = containerRef.current!.getBoundingClientRect();
    return {
      x: Math.min(Math.max(e.clientX - b.left, 0), b.width),
      y: Math.min(Math.max(e.clientY - b.top, 0), b.height),
    };
  }

  function onMouseDown(e: React.MouseEvent) {
    const p = pos(e);
    dragStart.current = p;
    setRect({ x: p.x, y: p.y, w: 0, h: 0 });
  }

  function onMouseMove(e: React.MouseEvent) {
    if (!dragStart.current) return;
    const p = pos(e);
    setRect({
      x: Math.min(dragStart.current.x, p.x),
      y: Math.min(dragStart.current.y, p.y),
      w: Math.abs(p.x - dragStart.current.x),
      h: Math.abs(p.y - dragStart.current.y),
    });
  }

  function onMouseUp() {
    dragStart.current = null;
  }

  const hasValidRect = !!rect && rect.w >= 8 && rect.h >= 8;

  function confirm() {
    if (!hasValidRect || !imgRef.current || !rect) return;
    const img = imgRef.current;
    // img.width/height are the rendered (display) box; naturalWidth/Height
    // are the real screenshot resolution — scale the drag rect from
    // display coordinates up to the real image before cropping.
    const scale = img.naturalWidth / img.width;
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(rect.w * scale);
    canvas.height = Math.round(rect.h * scale);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(
      img,
      rect.x * scale,
      rect.y * scale,
      rect.w * scale,
      rect.h * scale,
      0,
      0,
      canvas.width,
      canvas.height,
    );
    onConfirm(canvas.toDataURL('image/png'));
  }

  return (
    <div className="flex flex-col gap-2 p-3 border-b border-[var(--bd)] bg-[var(--surface)]">
      <p className="text-xs text-[var(--tx7)]">{t.dragToSelect}</p>
      <div
        ref={containerRef}
        className="relative select-none border border-[var(--bd)] rounded-lg overflow-hidden cursor-crosshair"
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
      >
        <img ref={imgRef} src={dataUrl} alt={t.dragToSelect} className="w-full h-auto block" draggable={false} />
        {rect && (
          <div
            className="absolute border-2 border-[var(--indigo)] pointer-events-none"
            style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h, background: 'rgba(129,140,248,0.15)' }}
          />
        )}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!hasValidRect}
          onClick={confirm}
          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-[var(--indigo)] text-white disabled:opacity-50"
        >
          {t.useThisRegion}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs font-medium px-3 py-1.5 rounded-lg border border-[var(--bd)] text-[var(--tx3)]"
        >
          {t.cancel}
        </button>
      </div>
    </div>
  );
}
