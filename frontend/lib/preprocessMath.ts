/**
 * preprocessMath
 *
 * remark-math v6 only understands $...$ and $$...$$ delimiters.
 * GPT-4o often outputs \[...\] (display) and \(...\) (inline) regardless
 * of instructions. This function converts them before ReactMarkdown runs.
 *
 * Also collapses stray leading/trailing whitespace inside math blocks so
 * KaTeX doesn't get confused by indented equations.
 */
export function preprocessMath(content: string): string {
  // \[ ... \]  →  $$\n...\n$$  (display / block math)
  content = content.replace(
    /\\\[\s*([\s\S]*?)\s*\\\]/g,
    (_m, math: string) => `\n$$\n${math.trim()}\n$$\n`,
  );

  // \( ... \)  →  $...$  (inline math)
  content = content.replace(
    /\\\(\s*([\s\S]*?)\s*\\\)/g,
    (_m, math: string) => `$${math.trim()}$`,
  );

  // Bare [ ... ] used by GPT-4o as display math delimiters.
  // Only convert when the content contains a LaTeX command (\word) so we don't
  // accidentally convert Markdown links ([text](...)) or plain bracketed text.
  // The (?!\() negative lookahead skips [text]( which is a Markdown link.
  content = content.replace(
    /\[([^\[\]]+?)\](?!\()/g,
    (match, inner) => {
      if (/\\[a-zA-Z]/.test(inner)) {
        return `\n$$\n${inner.trim()}\n$$\n`;
      }
      return match;
    },
  );

  return content;
}
