# 0002 — Teachable-friend pivot, story companion, wake-word shortlist, LAN-only parent UI

Date: 2026-10-13
Status: Accepted
Supersedes: parts of `docs/product_spec.md` section 7 (see below) — the
spec file itself stays verbatim as the product owner's original
document; this record is where the deviation and its rationale live.

## Context

Following Milestone 0, the product owner reconsidered the teaching model
and several open items from `docs/decisions/0001-milestone-0-scope.md`.
Four decisions came out of that discussion.

## Decisions

### 1. Teachable-friend replaces the tutor-style Education Engine

Spec section 7 asked for a deterministic multiplication-practice activity
with in-code answer validation. The product owner instead wants Chitti to
be a peer the *child* teaches — grounded in the "protégé effect" /
learning-by-teaching research (explaining a concept to a listener
improves the explainer's own understanding more than being taught it).

Architecturally this **removes the deterministic answer-key requirement**
for the MVP: there's no "activity" being graded, so
`companion_robot/education/`'s original scope (spec section 7's
`start_activity`/`submit_answer`/etc. interface) is not being built.
Instead this becomes a **Conversation Service persona pattern**: Chitti
plays a curious peer ("wait, why does that happen?", "can you show me?"),
asks genuine-sounding follow-ups, and occasionally reflects confusion to
prompt the child to explain further. No correctness grading exists
because there's nothing to grade.

This does **not** remove the Safety layer's job: whatever the child
"teaches" Chitti, the Safety layer still screens anything Chitti echoes
back before it's spoken, so an unsafe or false claim isn't uncritically
repeated (spec section 5 still applies in full).

### 2. Story companion: transcript-grounded story Q&A

New capability: Chitti listens to a story being read aloud (or reads one
itself) and answers the child's questions about it — grounded *only* in
that story's actual content, not general model knowledge, to avoid
answers drifting outside what was actually read.

Mechanism: the story is captured as a transcript and held as
**conversation context** (spec section 6, category 1 — temporary,
session-only) and fed back to the `LanguageModelBackend` as grounding
context for any question about it. Not a durable memory by default; a
child's favorite stories could become a `PERSONAL_PREFERENCE` memory
later if explicitly saved, but that's not required for this capability
to work.

No camera/OCR is introduced — this relies on listening to the story being
read aloud (ASR transcript), not visually reading a physical page, which
stays consistent with spec section 2.2's camera exclusion.

### 3. Wake word: child picks from a vetted shortlist, not an arbitrary custom word

Most efficient on-device wake-word engines (openWakeWord, Porcupine) need
a trained model per wake word — a child can't just say any word and have
it work. Decision: ship with a short list (5-10 names) the chosen engine
already supports well; the child picks one of those as Chitti's name and
wake word, rather than custom-training on an arbitrary word. Revisit
custom per-word training later if this matters enough to justify the
added setup friction and on-device training step.

The parent gets to approve/reset the chosen name before it goes live
(risk register: inappropriate name choice).

### 4. Parent controls: local web UI, LAN-only, PIN-gated from first boot

Not a cloud account/companion-app system. The robot itself serves a local
web UI (same Flask-on-a-background-thread pattern already proven in
`pixel-ai/photo_receiver.py`), reachable only from devices on the same
home WiFi network — **never port-forwarded or exposed to the public
internet**. This matches spec section 10's "avoid complex infrastructure
... unless a demonstrated requirement justifies it" and avoids the much
larger compliance surface a cloud account system would add (user
accounts, remote auth at scale, additional hosting/data-flow
documentation).

Concrete pieces:
- **Discovery**: mDNS (Avahi) advertises the robot at a `.local` hostname
  (e.g. `chitti.local`) so the parent doesn't need to know an IP address.
- **First-boot onboarding**: before the robot knows the home WiFi, it
  briefly broadcasts its own temporary setup hotspot (same pattern as
  smart-home devices); the parent connects once, enters home WiFi
  credentials *and* sets the parent PIN, then the hotspot disappears.
- **Auth**: PIN-gated from the very first boot, not an afterthought —
  closes risk register #8. Login attempts are rate-limited.
- **Explicit non-goal for this version**: remote (away-from-home) access.
  Confirmed with the product owner as LAN-only for v1 — if remote
  management is wanted later, it needs a cloud relay or companion app,
  which is a materially bigger, more compliance-heavy build, scoped
  separately rather than bolted on now.

## Consequences for existing docs

- `architecture.md` updated: Education Engine section replaced/amended,
  new Parent Controls (local web UI) section added, wake-word note added
  under Voice architecture, alarms noted under Reminder Service.
- `risk_register.md` #8 updated: mitigation now has a concrete plan
  (PIN from first boot + rate limiting) rather than being fully open.
- `product_spec.md` is left untouched (verbatim source document) — this
  record is the authoritative note that section 7's specific first
  activity is superseded for the MVP.

## Open follow-ups

- Final shortlist of wake-word-engine-supported names to offer the child.
- Exact alarm alert design (volume/sustain/snooze voice commands) —
  functional detail for whichever milestone implements the Reminder
  Service.
- Whether "things Chitti learned from the child" should ever become a
  durable, reviewable memory, or always stay session-only.
