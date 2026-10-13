"""Parent Controls (spec section 3.2.H) -- Milestone 5.

Owns network/cloud configuration, memory/retention settings, memory
review and deletion, feature toggles, device status, and data export.

Per decision 0002: a local web UI served by the robot itself (same
Flask-on-a-background-thread pattern as pixel-ai/photo_receiver.py),
discovered via mDNS (e.g. chitti.local), PIN-gated from first boot (set
during a temporary setup-hotspot onboarding flow), rate-limited login,
explicitly LAN-only -- never port-forwarded or exposed beyond the home
network. The auth *plan* is decided (docs/risk_register.md #8); nothing
is built yet.
"""
