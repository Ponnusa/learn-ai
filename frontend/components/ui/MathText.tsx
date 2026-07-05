'use client';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { preprocessMath } from '@/lib/preprocessMath';
import type { ComponentPropsWithoutRef } from 'react';

const INLINE_COMPONENTS = {
  p: ({ children, ...props }: ComponentPropsWithoutRef<'p'>) => <span {...props}>{children}</span>,
};

/**
 * Renders markdown with full LaTeX / KaTeX math support.
 * - Default (block): paragraph elements, suitable for summaries and explanations.
 * - inline=true: wraps <p> as <span> so it can live inside a <p> or <button>.
 */
export function MathText({
  children,
  inline = false,
}: {
  children: string | null | undefined;
  inline?: boolean;
}) {
  if (!children) return null;
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={inline ? INLINE_COMPONENTS : undefined}
    >
      {preprocessMath(children)}
    </ReactMarkdown>
  );
}
