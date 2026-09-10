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
  just type a question in the box at any time.
- **Quiz** — "🎯 Quiz me on this" from the selection card, or the
  "Quiz me on this (LearnX)" right-click entry (auto-runs, no extra click).
  Inline multiple-choice, submit, see score + explanations.
- **Context menu** — right-click a selection for the same two entry points
  as the floating pill, for pages where the pill is awkward to use.
- **Optional sign-in** — email/password (not magic-link or Google OAuth:
  both of those redirect through a web page, and the resulting token would
  land in the *web app's* storage, not somewhere this extension can read —
  see `src/panel/GenieAuth.tsx`'s header comment). Not required; anonymous
  usage works the same as the web app's anonymous flow, just with lower
  limits, and signing in switches to the account's own daily limits.

## What's not here yet

PDF support is the remaining later phase — see the project's implementation
plan for the full sequence.

## Before ever publishing

The `key` field in `public/manifest.json` is a **dev-only** convenience key
(paired with the gitignored `.dev-key.pem`) that exists purely so the
extension ID stays stable across unpacked reloads while testing. Generate a
fresh keypair before any real Chrome Web Store submission — don't ship this
one.
