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

  return content;
}
