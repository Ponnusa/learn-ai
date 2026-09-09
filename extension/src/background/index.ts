// Background service worker — lightweight relay only. It does NOT call the
// backend itself: the side panel (a genuine chrome-extension:// origin) does
// that directly. This worker's job is just wiring the browser-chrome parts
// together: open the side panel on toolbar-icon click, and when the content
// script reports a text selection, open the panel and hand it the selected
// text so the panel can seed a chat message with it.

chrome.action.onClicked.addListener((tab) => {
  if (tab.windowId != null) chrome.sidePanel.open({ windowId: tab.windowId });
});

interface SelectionMessage {
  type: 'GENIE_SELECTION';
  text: string;
  pageTitle: string;
  pageUrl: string;
}

// Last selection, kept in memory so the panel can pull it right after
// opening (message-passing to a panel that isn't open yet would be lost).
let pendingSelection: SelectionMessage | null = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message?.type) {
    case 'GENIE_SELECTION': {
      pendingSelection = message as SelectionMessage;
      const windowId = sender.tab?.windowId;
      if (windowId != null) chrome.sidePanel.open({ windowId });
      // Also forward live, in case the panel is already open and listening.
      // `type` must come AFTER the spread — message.type is 'GENIE_SELECTION',
      // and object spread overwrites earlier keys, so putting it first here
      // silently reverted the forwarded type back to 'GENIE_SELECTION' and
      // the panel's 'GENIE_SELECTION_FORWARD' listener never matched.
      chrome.runtime.sendMessage({ ...message, type: 'GENIE_SELECTION_FORWARD' }).catch(() => {
        // No listener yet (panel not open) — fine, it'll pull pendingSelection on mount.
      });
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
