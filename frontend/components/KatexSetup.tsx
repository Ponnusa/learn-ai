'use client';
// Side-effect only: registers \ce{} and other mhchem commands with KaTeX globally.
// Must be a client component so it runs during SSR of client components AND on
// the browser — ensuring mhchem is registered before any rehype-katex rendering.
import 'katex/contrib/mhchem';

export function KatexSetup() { return null; }
