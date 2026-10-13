# 0014 — Parent Controls: local PIN-gated web UI

Date: 2026-10-13
Status: Accepted

## Context

Sixth real feature, continuing the hardware-independent build order.
Implements the local web UI architecture.md and decisions 0002/0003
already designed: PIN-gated, LAN-only, served by the robot itself.

## What was built

- `parent_controls/auth.py`: `PinRepository` (PIN hashed via werkzeug's
  `generate_password_hash`/`check_password_hash` — never rolling custom
  crypto, never storing plaintext), `RateLimiter` (server-side lockout,
  deliberately not cookie/session-based), `load_or_create_secret_key()`
  (persists the Flask session-signing key across restarts — a fixed or
  regenerated-every-boot key would let sessions be forged or would log
  everyone out on every restart).
- `parent_controls/profiles.py`: `ChildProfile` + `ChildProfileRepository`
  — the actual entity `child_profile_id` has referred to throughout
  `memory/` and `reminders/` since decision 0003, now with somewhere
  real to live.
- `parent_controls/stories.py`: `StoryRecord` + `StoryRepository` — a
  shared story library (not per-child), matching architecture.md's
  "preloaded story library" framing.
- `parent_controls/app.py`: `create_app()` — the Flask app itself, same
  Flask-on-a-background-thread pattern as `pixel-ai/photo_receiver.py`.
  Routes: setup (first-boot PIN creation), login/logout, dashboard,
  child-profile CRUD, story CRUD, and memory review/deletion per child
  (built on the existing `MemoryRepository` from decision 0007).
- **Hand-rolled CSRF protection**: a per-session token, generated on
  first render and checked on every POST. Closes a gap
  `security_threat_model.md` had explicitly flagged as open since
  Milestone 0 — chosen over adding `flask-wtf`/`flask-seasurf` to keep
  the dependency list lean for what's a genuinely simple check.
- 15 new unit tests (77 total passing) via Flask's test client — no
  real server, no real network. Two are worth calling out specifically:
  `test_rate_limit_is_server_side_not_reset_by_a_fresh_session` proves
  the lockout survives a brand-new client with fresh cookies hitting
  the *same app instance* (not just repeated requests from one client
  — the actual security property that matters), and
  `test_post_rejected_without_valid_csrf_token` proves a POST without
  the right token is rejected outright.

## Explicitly not built

Both require real network/radio hardware to build or verify honestly,
not just more code:
- **mDNS advertisement** (`chitti.local` discovery).
- **First-boot setup-hotspot onboarding** (the flow that lets the
  device join the home WiFi and set the PIN before any of this web UI
  is even reachable).

Also not built: TLS for the LAN connection (open item in
`security_threat_model.md`, deliberately deferred, not solved by
"plain HTTP on a trusted LAN" being the default without someone
deciding that on purpose), and file-permission hardening on the
persisted session-secret-key file.

## Consequences

- Risk register #8 and #8b updated from "plan decided, not built" to
  "mitigated in code," with the mDNS/onboarding and TLS gaps stated
  explicitly rather than implied as closed.
- `security_threat_model.md`'s parent-UI entry updated to reflect what's
  actually built vs. still open.
