# LearnX Genie (Chrome extension) — Phase 1

Select text on any webpage, ask LearnX to explain it or walk you through it.
Reuses the exact same anonymous-session/credit model as the web app (see
`backend/routers/sessions.py`, `backend/services/credits.py`) — no login
required, same 8-message lifetime cap before a sign-in nudge.

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
a small "✨ Ask LearnX" pill should appear near the selection. Click it to
open the side panel with that text ready to send.

## What's not here yet

Quiz generation, PDF support, the context-menu entry point, and optional
sign-in are later phases — see the project's implementation plan for the
full sequence. This phase is deliberately just the smallest working slice:
select text → get an adaptive-teaching reply, with the same ladder/eureka
visuals as the app.

## Before ever publishing

The `key` field in `public/manifest.json` is a **dev-only** convenience key
(paired with the gitignored `.dev-key.pem`) that exists purely so the
extension ID stays stable across unpacked reloads while testing. Generate a
fresh keypair before any real Chrome Web Store submission — don't ship this
one.
