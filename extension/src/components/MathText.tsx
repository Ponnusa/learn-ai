// Ported from frontend/components/ui/MathText.tsx (katex.min.css import
// dropped — main.tsx already imports it once for the whole panel bundle).
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { preprocessMath } from '../lib/preprocessMath';
import { KATEX_OPTIONS } from '../lib/mathConfig';
import type { ComponentPropsWithoutRef } from 'react';

const INLINE_P: Components['p'] = ({ children, ...props }: ComponentPropsWithoutRef<'p'>) => (
  <span {...props}>{children}</span>
);

/**
 * Renders markdown with full LaTeX / KaTeX math (and chemistry, via
 * mathConfig.ts's mhchem registration) support.
 * - Default (block): paragraph elements, suitable for full replies.
 * - inline=true: wraps <p> as <span> so it can live inside a <p> or <button>
 *   (quiz questions/options/explanations).
 * - components: extra ReactMarkdown component overrides (e.g. GenieMessage's
 *   ```smiles code-block -> SmilesBlock render), merged with the inline `p`
 *   override when both are given.
 */
export function MathText({
  children,
  inline = false,
  components,
}: {
  children: string | null | undefined;
  inline?: boolean;
  components?: Components;
}) {
  if (!children) return null;
  const merged: Components | undefined =
    inline || components ? { ...(inline ? { p: INLINE_P } : {}), ...components } : undefined;
  return (
    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]} components={merged}>
      {preprocessMath(children)}
    </ReactMarkdown>
  );
}
