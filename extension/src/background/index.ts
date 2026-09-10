// Background service worker — lightweight relay only. It does NOT call the
// backend itself: the side panel (a genuine chrome-extension:// origin) does
// that directly. This worker's job is just wiring the browser-chrome parts
// together: open the side panel (toolbar icon, selection pill, or the
// right-click context menu), and hand it whatever text triggered that so
// the panel can seed a chat message (or auto-run a quiz) with it.

chrome.action.onClicked.addListener((tab) => {
  if (tab.windowId != null) chrome.sidePanel.open({ windowId: tab.windowId });
});

const ASK_MENU_ID = 'genie-ask';
const QUIZ_MENU_ID = 'genie-quiz';

chrome.runtime.onInstalled.addListener(() => {
  // Menu items are created once on install/update, not on every service-
  // worker wake — chrome.contextMenus.create throws "duplicate id" if
  // called again for an id that already exists, and worker wake-ups happen
  // far more often than installs.
  chrome.contextMenus.create({
    id: ASK_MENU_ID,
    title: '✨ Ask LearnX about "%s"',
    contexts: ['selection'],
  });
  chrome.contextMenus.create({
    id: QUIZ_MENU_ID,
    title: '🎯 Quiz me on this (LearnX)',
    contexts: ['selection'],
  });
});

interface SelectionPayload {
  text: string;
  pageTitle: string;
  pageUrl: string;
  action?: 'quiz'; // set when the entry point already expressed clear intent
                    // (right-click "Quiz me on this") — the panel auto-runs
                    // the quiz instead of waiting for a button click.
}

interface SelectionMessage extends SelectionPayload {
  type: 'GENIE_SELECTION';
}

// Last selection, kept in memory so the panel can pull it right after
// opening (message-passing to a panel that isn't open yet would be lost).
let pendingSelection: SelectionMessage | null = null;

function deliverSelection(payload: SelectionPayload, windowId: number | undefined) {
  const message: SelectionMessage = { type: 'GENIE_SELECTION', ...payload };
  pendingSelection = message;
  if (windowId != null) chrome.sidePanel.open({ windowId });
  // Also forward live, in case the panel is already open and listening.
  // `type` must stay on `message` (not re-spread after) — see the fix note
  // in git history: spreading an object with its own `type` AFTER an
  // explicit `type:` key silently overwrites it.
  chrome.runtime.sendMessage({ ...message, type: 'GENIE_SELECTION_FORWARD' }).catch(() => {
    // No listener yet (panel not open) — fine, it'll pull pendingSelection on mount.
  });
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!info.selectionText) return;
  deliverSelection(
    {
      text: info.selectionText,
      pageTitle: tab?.title ?? '',
      pageUrl: tab?.url ?? info.pageUrl ?? '',
      action: info.menuItemId === QUIZ_MENU_ID ? 'quiz' : undefined,
    },
    tab?.windowId,
  );
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message?.type) {
    case 'GENIE_SELECTION': {
      const { text, pageTitle, pageUrl, action } = message as SelectionMessage;
      deliverSelection({ text, pageTitle, pageUrl, action }, sender.tab?.windowId);
      sendResponse({ ok: true });
      return;
    }
    case 'GENIE_GET_PENDING_SELECTION': {
      sendResponse(pendingSelection);
      pendingSelection = null; // consume once — avoid re-seeding on every panel remount
      return;
    }
  }
});
