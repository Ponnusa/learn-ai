# LearnX Genie (Chrome extension)

Select text on any webpage, ask LearnX to explain it, walk you through it,
or quiz you on it. Reuses the exact same anonymous-session/credit model as
the web app (see `backend/routers/sessions.py`, `backend/services/credits.py`)
— no login required, same limits before a sign-in nudge (8 messages, 1 quiz,
both lifetime for an anonymous session).

## Build

```
npm install
npm run build
```

Builds into `dist/`: `manifest.json` + `panel.html`/assets (side panel SPA)
+ `background.js` + `content.js`.

## Load it (unpacked, for development)

1. `chrome://extensions` → enable **Developer mode** → **Load unpacked** →
   select `extension/dist`.
2. Note the extension ID Chrome assigns it. `manifest.json` ships with a
   fixed dev `key`, so this ID stays the same across reloads — you only
   need to do the next step once.
3. Add `chrome-extension://<that-id>` to the backend's `EXTRA_ALLOWED_ORIGINS`
   env var (comma-separated, see `backend/config.py`) and restart the
   backend. Without this, every request from the panel fails CORS.
4. Point `src/lib/api.ts`'s `API_BASE` at whichever backend you're testing
   against (defaults to `http://localhost:8000`).

## Try it

Select a sentence of text on any real webpage (not the LearnX app itself) —
a small "✨ Ask LearnX" pill should appear near the selection. Click it (or
right-click the selection and pick "Ask LearnX" / "Quiz me on this") to open
the side panel with that text ready to send, or to auto-generate a quiz.

## What's here

- **Chat** — select text → "Help me understand it" (nudges guided discovery,
  the ladder/eureka experience) or "Just explain it" (direct answer). Or
  just type a question in the box at any time. Every reply carries the same
  action toolbar as the web app's chat (minus video generation, which genie
  doesn't offer): ✏️ Quiz me, 🧭 Walk me through it, suggestion chips + 💡
  Show me an example, ↓ Simplify this / ↑ Go deeper, read-aloud, copy — all
  hidden while a guided-discovery question is still awaiting an answer,
  same as the app.
- **Formulas & structures** — physics/chemistry/math formulas render via
  KaTeX (ported `preprocessMath`/`mathConfig`/`MathText` from
  `frontend/lib/` and `frontend/components/ui/`), and organic chemistry
  structures written as ` ```smiles ` code blocks render as real 2D
  diagrams via `smiles-drawer` (ported `SmilesBlock.tsx`) — same as the web
  app's chat, including its \ce{} chemistry-notation trade-off (stripped to
  plain text rather than rendered, for the same reliability reason the app
  makes that call).
- **Quiz** — "🎯 Quiz me on this" from the selection card, a per-reply
  "Quiz me" button, or the "Quiz me on this (LearnX)" right-click entry
  (auto-runs, no extra click). Inline multiple-choice; submit to see your
  score with correct answers and your mistakes highlighted (green/red,
  check/x icons — matches the web app's quiz results styling exactly).
  Doesn't "close" and discard the result — minimizes to a one-line score
  summary instead, expandable again any time.
- **Context menu** — right-click a selection for the same two entry points
  as the floating pill, for pages where the pill is awkward to use.
- **Screen clip (📎 in the input row)** — captures the visible tab
  (`chrome.tabs.captureVisibleTab`, no extra permission needed beyond the
  `host_permissions` the extension already has), then a drag-select crop
  UI (`ClipCapture.tsx`, mirroring `PDFViewerModal.tsx`'s region-capture
  UX) picks the region to ask about. Uploaded and sent as `image_url` —
  the same vision-based flow the web app's PDF handling already uses, just
  sourced from any on-screen content, not only PDFs. Chosen over a
  PDF-specific viewer deliberately: no pdf.js-in-extension complexity, no
  fighting Chrome's built-in PDF viewer blocking content scripts, and it
  works on anything visible (diagrams, worksheets, PDFs, whatever), not
  just PDFs.
- **Optional sign-in** — email/password (not magic-link or Google OAuth:
  both of those redirect through a web page, and the resulting token would
  land in the *web app's* storage, not somewhere this extension can read —
  see `src/panel/GenieAuth.tsx`'s header comment). Not required; anonymous
  usage works the same as the web app's anonymous flow, just with lower
  limits, and signing in switches to the account's own daily limits.

## Before ever publishing

The `key` field in `public/manifest.json` is a **dev-only** convenience key
(paired with the gitignored `.dev-key.pem`) that exists purely so the
extension ID stays stable across unpacked reloads while testing. Generate a
fresh keypair before any real Chrome Web Store submission — don't ship this
one.
