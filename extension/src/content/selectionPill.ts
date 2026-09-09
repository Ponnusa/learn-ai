// Content script — plain DOM, zero framework/imports, to keep this bundle
// tiny (it's injected into every page). Watches for a text selection and
// shows a small floating pill near it; clicking the pill messages the
// background worker with the selected text, which opens the side panel.
// Never calls the backend directly (see src/lib/api.ts's header comment).

const MIN_SELECTION_LENGTH = 3;

let pill: HTMLButtonElement | null = null;

function removePill() {
  pill?.remove();
  pill = null;
}

function showPill(rect: DOMRect, text: string) {
  removePill();

  const btn = document.createElement('button');
  btn.textContent = '✨ Ask LearnX';
  btn.setAttribute('type', 'button');
  Object.assign(btn.style, {
    position: 'fixed',
    left: `${Math.max(8, Math.min(rect.left, window.innerWidth - 140))}px`,
    top: `${Math.max(8, rect.top - 36)}px`,
    zIndex: '2147483647',
    padding: '6px 12px',
    fontSize: '13px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontWeight: '600',
    color: '#fff',
    background: '#4f46e5',
    border: 'none',
    borderRadius: '999px',
    boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
    cursor: 'pointer',
  } satisfies Partial<CSSStyleDeclaration>);

  btn.addEventListener('mousedown', (e) => e.preventDefault()); // don't steal the selection on click
  btn.addEventListener('click', () => {
    chrome.runtime.sendMessage({
      type: 'GENIE_SELECTION',
      text,
      pageTitle: document.title,
      pageUrl: location.href,
    });
    removePill();
  });

  document.documentElement.appendChild(btn);
  pill = btn;
}

document.addEventListener('mouseup', () => {
  // Defer a tick so the browser's own selection state has settled.
  setTimeout(() => {
    const selection = window.getSelection();
    const text = selection?.toString().trim() ?? '';
    if (text.length < MIN_SELECTION_LENGTH || !selection || selection.rangeCount === 0) {
      removePill();
      return;
    }
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) {
      removePill();
      return;
    }
    showPill(rect, text);
  }, 0);
});

document.addEventListener('mousedown', (e) => {
  if (pill && e.target !== pill) removePill();
});
