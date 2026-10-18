# 0055 — Evidence-based Reading Partner feedback

Date: 2026-10-18
Status: Accepted

## Context

External feedback on a real Pi session (building on decision 0054's
live-bug fixes) made a sharper point than "the sound list was too
long": even capped at 3 sounds, naming phonics labels disconnected
from what the child actually read "feels automated rather than tied
to the child's actual reading," and announcing newly-crossed mastery
thresholds after every single book risks overclaiming confidence from
one read. The recommendation: replace the sound-list sentence with
one short, evidence-based response tied to the specific read -- name
a real word the child said correctly, or the one word still worth
practicing, rather than a label taxonomy.

A separate correction, not a change: the same feedback claimed Chitti
"doesn't know which words were wrong." That's not accurate for what's
already built -- `reading/alignment.py`'s `assess()` already
classifies every word as correct/substitution/omission/insertion with
its exact position, and already drives both mastery updates and hint-
word selection (decision 0052). The real gap was narrower: that detail
was never *cited* in the spoken feedback, only used internally.

## What shipped

**`reading/schema.py`**: `AssessmentResult` gained `correct_words: list[str]`
-- the expected words actually read correctly, in order. **`reading/alignment.py`**'s
`assess()` now populates it from the same `ops` list it already builds (`[op.expected
for op in ops if op.kind == CORRECT and op.expected]`) -- no new
alignment logic, just exposing data that already existed internally.

**`reading/feedback.py`**: `build_reading_feedback()` replaces the
mastery-sound-list sentence entirely with:
- If the hint-and-retry loop (decision 0052) ran this turn and the
  child never got the word right, a gentle callout to that specific
  word ("Let's keep practicing the word 'sat' together next time.") --
  passed in via a new `hint_word` parameter, `None` by default.
- Otherwise, a real standout word the child actually read correctly
  (`_standout_word()`: the longest correctly-read word that's at
  least 4 letters, so a short word like "a"/"is" never gets an
  artificial callout). If nothing qualifies, no second sentence --
  the warm accuracy-tier opener alone is a complete response.

Grapheme mastery itself is **unaffected** -- `reading/mastery.py`
still updates and persists `reading_grapheme_mastery` every turn
exactly as before; it's simply no longer announced out loud after
every single book. A parent-facing mastery view is still the
explicitly deferred Parent Controls progress report (decision 0051).

**`voice_loop_demo.py`**'s `_run_reading_partner()`: tracks whether
the hint loop's retry ever succeeded (`hint_resolved`) and passes
`hint_word` to `build_reading_feedback()` only when it didn't --
avoids repeating a word the child already got right moments earlier
in the same turn.

This supersedes decision 0054's cap-and-filter fix to the same
sentence, which is now dead code and removed (`_spoken_list()`,
`_MAX_SPOKEN_SOUNDS`, the `isalpha()` sentinel filter) -- the whole
mechanism they patched is gone, not just bounded.

## Consequences

`test_reading_feedback.py` rewritten for the new contract (standout-
word citation, the no-notable-word case, the hint-word-mentioned vs.
hint-word-resolved cases) -- the decision 0054 tests for sentinel-
filtering and the 3-item cap were removed along with the code they
tested. One new test in `test_reading_alignment.py` for
`correct_words`. Two `test_voice_loop_demo_intent.py` end-to-end tests
extended/added: the unresolved-hint test now asserts the hint word is
named in the final feedback, and a new test drives a real "A little
bunny hops" read through `_run_reading_partner()` to confirm the
standout word ("little") actually reaches the spoken feedback.
Full suite: 426 passed, 1 skipped (pygame unavailable in this dev
environment, pre-existing).

Also tracked, not shipped here: the live-sync teleprompter question
this feedback also raised is logged as a dedicated future evaluation
in decision 0004's "Open follow-ups" (2026-10-18 entry) and cross-
referenced from decision 0053's "Not yet done" -- a real architecture
decision (new STT backend, changes to the audio capture layer and the
render loop), not something to bolt onto Reading Partner directly.

## Not yet done

- Reading comprehension checking and the parent progress report --
  unaffected, still open per decision 0051/0054.
- Streaming/live-sync word highlighting -- tracked in decision 0004,
  not evaluated yet.
