// Ported verbatim from frontend/lib/mathConfig.ts.
// Side-effect: registers \ce{...} chemistry notation with KaTeX globally.
// Must be imported before any rehype-katex rendering happens. (The app
// does this via a no-op KatexSetup component for Next.js SSR ordering —
// the panel has no SSR, so importing it here once is enough.)
import 'katex/contrib/mhchem';

/** Options passed to rehype-katex wherever math is rendered in the panel.
 *  throwOnError: false — broken formulas show a red error inline instead of crashing the component.
 *  strict: false      — allow commands KaTeX doesn't know without throwing (e.g. rare physics macros).
 */
export const KATEX_OPTIONS = {
  throwOnError: false,
  strict: false,
} as const;
