# 0127 — Intent-switching: fix false-positive matches, self-correcting yes/no, and de-duplicate the 5 call sites

Date: 2026-10-26

Status: Accepted

## Context

A detailed external review of the mode-switching system (decision
0042's three-tier `_detect_switch_intent()`, `intent/router.py`'s
phrase/keyword matching, and the 5 mode loops that call it) raised
nine numbered concerns and a large proposed redesign (a structured
decision-object/controller architecture with CONTINUE/HELP/SWITCH/
CLARIFY/STOP/PAUSE/RESUME/REPEAT actions).

Each concern was checked directly against the real code before
deciding what to build:

**Confirmed, real bugs:**
- **Negation**: `detect_intent_phrase()` uses unanchored `.search()`,
  so "Don't tell me a story." matches `_STORY_PATTERN` just as
  readily as "Tell me a story." does -- the "Don't" in front is never
  considered.
- **Keyword-gate substring matching**: `mentions_activity_keyword()`
  used plain substring checks -- "read" matches inside "already",
  "sing" matches inside "using" -- each wrongly paying for the LLM
  classification fallback on ordinary, unrelated sentences.
- **Yes/no self-correction**: `classify_affirmative()`'s "first
  signal word wins" rule (decision 0046's own addendum, there to fix
  a *different* failure) reads "Okay, actually no." as a yes, because
  "okay" is the first signal word and the correction right after it
  is never considered.

**Overstated or not reproducible against the real code:**
- Story-vs-Reading-Partner ambiguity: `_READ_PATTERN`'s own docstring
  already explains it's deliberately checked *after* `_STORY_PATTERN`
  so "I want to read a story" resolves to STORY on purpose (decision
  0051) -- not a pattern/comment mismatch, already working as
  documented.
- "5 separate implementations of the switching decision": all 5 mode
  loops already call the exact same `_detect_switch_intent()` /
  `_confirm_switch()` functions. What *was* duplicated 5 times is one
  small 4-line reaction block, not the decision logic itself.

**Not buildable right now, not attempted:**
- Interrupting Lullaby playback or mid-story-reading on a stop/pause
  command: this file's own top-of-module docstring says the Pi 1 B+
  has no physical button and a real wake-word engine is currently
  blocked on this hardware (no ARMv6 wheel for openWakeWord;
  Porcupine unconfirmed) -- there is no live microphone monitoring
  while Chitti is talking or singing, so there is nothing for a
  software fix to interrupt yet.
- The structured decision-object/controller redesign (PAUSE/RESUME/
  REPEAT/HELP as first-class actions): nothing in this codebase has a
  pause/resume concept for TTS playback or tracks "the last utterance"
  to repeat -- building a general action enum with actions nothing
  underneath can perform is exactly the premature-abstraction trap
  this project's own prior decisions (e.g. 0123) have consistently
  avoided.

## What shipped

**`intent/router.py`**:
- `detect_intent_phrase()` rewritten as a loop over (pattern, label)
  pairs; a match is only accepted if `_negated_before()` (a small,
  fixed lookback window, a small fixed negation-word list) doesn't
  find a negation word in the few words right before the matched
  phrase. Deliberately narrow -- catches "don't X"/"let's not X"
  right before the activity verb, not general negation-scope parsing.
- `mentions_activity_keyword()` now tokenizes to whole words and
  checks whether a keyword *starts* a word (`word.startswith(keyword)`),
  not whether it's a bare substring -- blocks "read" inside "already"
  and "sing" inside "using" while still matching legitimate
  inflections like "talking" (from "talk") and "teaching" (from
  "teach"), which an exact-whole-word-only fix (tried first, see
  "Errors and fixes" below) would have broken.
- `classify_affirmative()` now tokenizes via regex (`re.findall`)
  instead of `.split()` + per-word strip -- correctly separates words
  glued together by punctuation with no surrounding space (e.g. an
  em-dash). It also now looks for a correction marker ("actually",
  "wait", "mean") and, if found, only considers signal words *after*
  the last one -- otherwise unchanged first-signal-word-wins behavior,
  so decision 0046's own original fix still applies.

**`voice_loop_demo.py`**: new `_maybe_switch_mode()` helper extracts
the one genuinely duplicated piece -- "detect, then confirm if not
confident, return the mode to switch to or None" -- used at all 5
mode-loop call sites, each shrunk from 7 lines to 4. Pure refactor, no
behavior change.

## Errors and fixes

**Self-caught, before committing**: the first version of
`mentions_activity_keyword()`'s fix used exact whole-word set
membership (`words & _ACTIVITY_KEYWORDS`), not prefix matching. Running
the full suite exposed 2 failures AND one test that hung indefinitely:
`test_run_teachable_friend_switches_to_just_chat_with_no_confirmation()`
mocks `_capture_and_transcribe()` to always return the same text
("my friend is not talking to me"); with the gate no longer
recognizing "talking" as activity-related (since it isn't the exact
word "talk"), `_detect_switch_intent()` returned `(None, False)`
instead of switching, so `_run_teachable_friend()`'s loop never broke
and looped forever on the same mocked input. Fixed by switching from
exact-word matching to prefix matching, which keeps the real fix
(mid-word substrings like "read" in "already") while preserving
legitimate suffixed forms ("talking", "teaching", "singing").

## Consequences

Added tests to `test_intent_router.py`: negation suppresses a
phrase match (and a non-negated "stop reading and tell me a story"
still resolves to STORY, proving the lookback window doesn't
over-trigger); the keyword gate ignores "already"/"using"-style
false positives; `classify_affirmative()` respects a self-correction
in 3 shapes, and a regression test confirming the original decision
0046 addendum case ("yes my friend is not talking to me...", no
correction marker) still resolves correctly.

Full suite: 722 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

Known minor edge case: prefix matching means "ready" now triggers the
activity-keyword gate (it starts with "read"), paying for an
occasional unnecessary LLM classification call on sentences like
"I'm ready for bed" -- a cost, not a correctness bug (the classifier
itself would say NONE). Not worth a special case for.

Explicitly not attempted, per the review above: cross-mode STOP/
PAUSE/RESUME/REPEAT controls, interruptible Lullaby/reading-aloud
playback, and the structured decision-object architecture -- all
blocked on push-to-talk hardware limits or solving for capabilities
that don't exist yet elsewhere in this codebase.
