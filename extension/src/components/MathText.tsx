// Ported from frontend/components/ui/MathText.tsx (katex.min.css import
// dropped — main.tsx already imports it once for the whole panel bundle).
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { preprocessMath } from '../lib/preprocessMath';
import { KATEX_OPTIONS } from '../lib/mathConfig';
import type { ComponentPropsWithoutRef } from 'react';

const INLINE_COMPONENTS = {
  p: ({ children, ...props }: ComponentPropsWithoutRef<'p'>) => <span {...props}>{children}</span>,
};

/**
 * Renders markdown with full LaTeX / KaTeX math (and chemistry, via
 * mathConfig.ts's mhchem registration) support.
 * - Default (block): paragraph elements, suitable for full replies.
 * - inline=true: wraps <p> as <span> so it can live inside a <p> or <button>
 *   (quiz questions/options/explanations).
 */
export function MathText({ children, inline = false }: { children: string | null | undefined; inline?: boolean }) {
  if (!children) return null;
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
      components={inline ? INLINE_COMPONENTS : undefined}
    >
      {preprocessMath(children)}
    </ReactMarkdown>
  );
}
