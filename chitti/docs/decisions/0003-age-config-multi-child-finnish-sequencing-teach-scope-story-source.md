# 0003 — Age config, multi-child profiles, Finnish sequencing, teach scope, story source

Date: 2026-10-13
Status: Accepted (one sub-item — profile-switching mechanism — still open, see below)

## Context

Answers to the six open/unclear items raised after auditing the docs for
staleness (see the conversation preceding this record; items 1-6
correspond to that list).

## Decisions

### 1. Age range is parent-configured, per child

Not a single fixed target age. The parent sets each child's age (or
age-band) via the parent web UI; this drives Teachable-Friend/Story
Companion vocabulary, pacing, and complexity. Lives on the **child
profile** (see decision 2), not as a global device setting.

### 2. Multiple child profiles, one physical device

Confirmed: siblings can share one Chitti, each with their own profile
(age, memory, preferences, learning/story history). This changes
`memory/schema.py`'s `MemoryRecord` — it needs to be scoped to a
specific child, not just one global child. Added `child_profile_id`
field now (typed only, no storage logic yet, consistent with Milestone
0's scope).

**Open sub-item, not resolved by this decision**: spec section 2.2
explicitly excludes "voice-based identity recognition of children" from
the MVP. That means Chitti **cannot** automatically tell Anna's voice
apart from Timmy's to silently pick the right profile — the spec forbids
exactly the mechanism that would make profile-switching invisible.
Some explicit, non-biometric switching mechanism is needed instead
(e.g. the child says a self-identifying phrase like "Hey Chitti, it's
Anna"; a physical button/press-and-hold per child; a parent-set default
per time-of-day; or a companion step in the local web UI before a
session). This is asked back to the user separately — see the
conversation immediately following this record — because it's a genuine
architectural fork, not something to guess at.

### 3. Finnish is a committed requirement, sequenced after English

Not optional, not merely "nice to have" — Finnish support is required
before any real/commercial launch (matches the target market in spec
section 0). It is **not** required for the very first working prototype;
English ships first for development velocity, Finnish is verified and
added before anything resembling a pilot. This resolves risk register
#7's framing: the risk isn't "maybe we need Finnish," it's "Finnish is
required and not yet verified for any candidate backend" — still open,
now with clearer urgency and sequencing.

### 4. Teachable-Friend: any topic, filtered for age-appropriateness; new "repeat what I say" capability

The child can teach Chitti about *anything*, not just STEM-adjacent
topics — widening the Safety layer's required coverage (it was already
supposed to screen everything Chitti echoes back; this confirms that
coverage must handle arbitrary subject matter, including profanity/bad
language filtering specifically called out by the product owner).

New capability: a "repeat what I say" mode (Chitti repeats back what the
child just said) — likely useful as a toddler-friendly language-play
game, common in companion-toy robots. **Critically, this is not a literal
unfiltered echo**: it must go through the same Safety-layer filtering as
any other Chitti speech. A child asking Chitti to repeat profanity or
unsafe content must be gently declined (e.g. "I don't say that word,
let's try a different one!"), not an exception carved out of the safety
boundary. This is a new, explicit risk-register entry (see below) because
an echo feature is an easy place to accidentally create a bypass if not
built carefully.

### 5. Story source: preloaded library + parent-uploaded via the web UI

Resolves the earlier open question in favor of the more reliable option:
**Chitti narrates** stories it already has a certain transcript for
(no ASR-transcription-of-a-child's-own-reading involved, avoiding that
accuracy risk entirely). Two sources for that transcript:
- A **preloaded story library** shipped with the device/product.
- **Parent-uploaded stories** via the local parent web UI (decision
  0002's LAN-only UI gains a story-management feature: upload, list,
  remove).

Parent-uploaded content is trusted as-is (the parent is the authorizing
adult) — this build does not content-moderate what a parent uploads for
their own child, only validates format/size at an engineering level.
Noted explicitly as an assumption, not silently decided.

### 6. Parent PIN recovery: "maybe needed" — left genuinely open

Not committed either way. A reasonable default to consider later: a
physical factory-reset mechanism on the device itself (same class of
solution as a router's reset button), which would also need `device/`
support. Not designed now; flagged so it isn't forgotten, not decided.

## Consequences for existing docs/code

- `memory/schema.py`: added `child_profile_id: str` to `MemoryRecord`.
- `architecture.md`: Story Companion section updated (narration from a
  known transcript, not ASR-of-child-reading); new Child Profiles note;
  Parent Controls section gains a story-upload mention; Teachable-Friend
  section gains the repeat-after-me note and the "any topic, age-filtered"
  scope.
- `risk_register.md`: new entries for the repeat-after-me bypass risk,
  the voice-ID-exclusion vs. multi-child-switching conflict (open), and
  Finnish's upgraded urgency.
- `docs/decisions/0001-...`'s open-items list: item 2 (wake-word vs.
  push-to-talk) was already resolved by decision 0002; this record
  resolves most of the "requirement not clear" list raised afterward,
  except the profile-switching mechanism.

## Still open after this decision

- **Profile-switching mechanism** (see item 2) — asked back to the user.
- Parent PIN recovery (item 6) — explicitly deferred, not decided.
- Carried over from 0001: final AI backend, `companion_robot` package
  name confirmation, who performs the legal/compliance review.
