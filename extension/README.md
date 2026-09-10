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
2. Note the extension ID Chrome assigns it. `manifest.json` has no `key`
   field (the Chrome Web Store rejects uploads that include one — it
   insists on assigning IDs itself), so the ID is derived from
   `extension/dist`'s own file path instead — that's still stable across
   reloads as long as you keep loading it from the same folder, you only
   need to do the next step once **per machine/checkout**.
3. Add `chrome-extension://<that-id>` to the backend's `EXTRA_ALLOWED_ORIGINS`
   env var (comma-separated, see `backend/config.py`) and restart the
   backend. Without this, every request from the panel fails CORS.
4. Point `src/lib/api.ts`'s `API_BASE` at whichever backend you're testing
   against (defaults to `http://localhost:8000`).

Once actually published through the Chrome Web Store, the live version gets
a **separate, permanent ID** assigned by the Store on first upload — that
one also needs adding to `EXTRA_ALLOWED_ORIGINS` (alongside your local dev
ID, if you want both to keep working against the same backend).

## Try it

Select a sentence of text on any real webpage (not the LearnX app itself) —
a small "✨ Ask LearnX" pill should appear near the selection. Click it (or
right-click the selection and pick "Ask LearnX" / "Quiz me on this") to open
the side panel with that text ready to send, or to auto-generate a quiz.

## What's here

- **Chat** — select text → "Help me understand it" (nudges guided discovery,
  the ladder/eureka experience) or "Just explain it" (direct answer). Or
  just type a question in the box at any time. Every reply carries the same
  action toolbar as the web app's chat: 🎬 Animate it, ✏️ Quiz me, 🧭 Walk
  me through it, suggestion chips + 💡 Show me an example, ↓ Simplify this
  / ↑ Go deeper, read-aloud, copy — all hidden while a guided-discovery
  question is still awaiting an answer, same as the app. Animate it is
  shown for toolbar parity, but genie doesn't generate video itself —
  clicking it shows a short notice pointing to learnx-ai.com instead.
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
- **Screen clip (crosshair icon in the input row)** — captures the visible tab
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
- **Response language** — a combo box in the header, same 6 languages and
  labels as the web app's Settings page (`frontend/translations/index.ts`).
  Defaults to a locally-remembered choice (or the browser's locale) and, on
  sign-in, snaps to the account's saved language, same precedence as
  `frontend/hooks/useLanguage.ts`. Changing it while signed in persists to
  the account via `PATCH /api/auth/language`, same endpoint the web app
  uses — so it's genuinely a shared setting, not a separate one. Every chat
  and quiz request now sends it; previously genie sent no `language` field
  at all and silently always replied in English regardless of the user's
  actual preference.
- **Branding** — two deliberately different identities. The **toolbar/
  manifest icon** (16/32/48/128px, `public/icons/`, via `sharp`) is the web
  app's own icon (`frontend/public/logo_source.png`) — this is what shows
  in the Chrome toolbar, `chrome://extensions`, and the side panel's own
  title strip (that last one is Chrome's own chrome, not something this
  code renders — its icon always follows the manifest, there's no way to
  point it at something else). The **genie mascot**
  (`assets-src/genie-mascot-source.png`, the master art; regenerate sizes
  from this if it ever changes) lives *inside* the chat surface only: the
  in-panel header icon, a brief branded splash on panel open
  (`public/branding/genie-mascot-240.png`, fades in/out, doesn't block the
  real session/auth bootstrap running underneath it), the empty-state
  illustration above the "select some text..." hint, and the eureka
  celebration (`EurekaBurst.tsx` — the mascot pops up as the confetti
  lands, with a real applause clip, `public/audio/eureka-applause.mp3`
  — a synthesized noise-burst clap was tried first but didn't sound
  convincing, so this is a licensed recording instead. The source file
  runs much longer than the ~4s confetti burst, so playback is faded out
  and stopped in sync with `EUREKA_BURST_DURATION` rather than left to run
  past the visual celebration; gated behind the same prefers-reduced-motion
  check the confetti already respects).
- **Continue in LearnX** — a link below the chat once there's something to
  continue, deep-linking to the actual conversation (`?conv=<id>`, the same
  param `frontend/app/page.tsx` already reads on load). Genuinely "continue
  there," not just a nudge — every conversation genie starts is a real
  conversation on the account/session. One caveat: this only round-trips
  cleanly for a signed-in user today — the web app has no URL param for
  picking up a specific *anonymous* session, so an anonymous user's link
  opens the app's own separate anonymous session, not this one's. Fixing
  that would be new web-app work, not something the extension alone can do.

## Publishing to the Chrome Web Store

1. `npm run build`, then zip the **contents** of `dist/` (not the `dist`
   folder itself — `manifest.json` must sit at the zip's root). PowerShell's
   `Compress-Archive` writes backslash path separators on Windows, which
   breaks nested folders (`icons/`, `audio/`, `branding/`) once Chrome
   unpacks it — use `python -m zipfile` or Python's `zipfile` module
   instead, which writes proper forward-slash paths:
   ```
   python -c "
   import zipfile, os
   with zipfile.ZipFile('learnx-genie.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
       for root, dirs, files in os.walk('dist'):
           for f in files:
               full = os.path.join(root, f)
               zf.write(full, os.path.relpath(full, 'dist').replace(os.sep, '/'))
   "
   ```
2. Upload `learnx-genie.zip` in the Developer Dashboard. `manifest.json`
   deliberately has **no `key` field** — the Store rejects uploads that
   include one, since it assigns IDs itself. (This used to have a fixed dev
   key for stable local-testing IDs; removed after hitting exactly this
   upload rejection. Local dev IDs are still stable per-checkout via
   `dist`'s own file path — see "Load it" above.)
3. After a successful upload, copy the ID the Store assigns and add
   `chrome-extension://<that-id>` to the backend's `EXTRA_ALLOWED_ORIGINS`
   — it's a different ID from whatever your local unpacked build uses.
