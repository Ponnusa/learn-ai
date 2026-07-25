'use client';
import { useEffect, useRef, useState } from 'react';
import SmilesDrawerNS from 'smiles-drawer';

interface Props {
  smiles: string;
}

export function SmilesBlock({ smiles }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    container.innerHTML = '';
    setError(null);

    const clean = smiles.trim();
    if (!clean) return;

    // Always light background — chemistry convention, readable in any app theme
    const svgDrawer = new SmilesDrawerNS.SvgDrawer({ width: 300, height: 220 });

    SmilesDrawerNS.parse(
      clean,
      (tree: unknown) => {
        const svg = svgDrawer.draw(tree, null, 'light') as SVGSVGElement;
        // Make the SVG fill its container width
        svg.style.width = '100%';
        svg.style.height = 'auto';
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.setAttribute('viewBox', svg.getAttribute('viewBox') ?? '0 0 300 220');
        container.appendChild(svg);
      },
      (err: Error) => {
        setError(err.message ?? 'Invalid SMILES');
      },
    );
  }, [smiles]);

  return (
    <div className="my-3 inline-block">
      {error ? (
        <span className="text-[11px] text-red-400 font-mono bg-[var(--ov1)] px-2 py-1 rounded">
          Invalid SMILES: {error}
        </span>
      ) : (
        <div
          ref={containerRef}
          title={smiles.trim()}
          className="bg-white rounded-xl border border-[var(--bd)] p-2 overflow-hidden"
          style={{ width: 220, minHeight: 160 }}
        />
      )}
    </div>
  );
}
