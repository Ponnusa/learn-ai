"""Parent Controls (spec section 3.2.H).

Owns network/cloud configuration, memory/retention settings, memory
review and deletion, feature toggles, device status, and data export.

Per decisions 0002/0003: a local web UI served by the robot itself
(same Flask-on-a-background-thread pattern as
pixel-ai/photo_receiver.py), PIN-gated from first boot, rate-limited
login, explicitly LAN-only -- never port-forwarded or exposed beyond
the home network.

- auth.py: PinRepository (hashed PIN, single-row settings table),
  RateLimiter (server-side lockout), load_or_create_secret_key()
  (persists the Flask session-signing key).
- profiles.py: ChildProfile + ChildProfileRepository.
- stories.py: StoryRecord + StoryRepository (shared story library).
- app.py: create_app() -- the Flask app itself. Hand-rolled CSRF
  protection (a per-session token checked on every POST) closes the
  gap flagged in docs/security_threat_model.md.

Not built, and not verifiable without real network/radio hardware: mDNS
advertisement (chitti.local) and the first-boot setup-hotspot
onboarding flow that lets the device join the home WiFi in the first
place -- both genuinely need real hardware to build or test honestly.
"""
