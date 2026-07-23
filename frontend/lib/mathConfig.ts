// Side-effect: registers \ce{...} chemistry notation with KaTeX globally.
// Must be imported before any rehype-katex rendering happens.
import 'katex/contrib/mhchem';

/** Options passed to rehype-katex wherever math is rendered in this app.
 *  throwOnError: false — broken formulas show a red error inline instead of crashing the component.
 *  strict: false      — allow commands KaTeX doesn't know without throwing (e.g. rare physics macros).
 */
export const KATEX_OPTIONS = {
  throwOnError: false,
  strict: false,
} as const;
