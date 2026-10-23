# 0096 — One combined reaction to a word family read, not one per word

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback, from a real hardware log: after the word-family
read ("can, plan, man, fan" for a family like "cat"/"bat"), Chitti
gave a separate full reaction to every single word in a row --
*"Yes! That's exactly it!"*, *"You got it!"*, *"Yes! That's exactly
it!"*, *"Yes! That's exactly it!"* -- four lines, each with its own
TTS/audio round trip, with **no child input between any of them**.
The report: *"i think its better for one feedback or work on the
error word."*

`_run_word_family_practice()`'s old loop (decision 0084's one-
capture-many-reactions shape) looped every family word and spoke
`random_correct_response()` or `incorrect_response()` for each one
individually, regardless of how many were actually correct -- a
clean read of a 4-word family meant four back-to-back praise lines.

## What shipped

**`voice_loop_demo.py`**, `_run_word_family_practice()`'s feedback
section, after the existing "nothing attempted at all" early return
(decision 0089, unchanged):

- **All words correct**: one combined line --
  `"Wow, you read all of them: {words}! Great job!"` -- instead of
  one praise line per word.
- **Some correct, some missed**: one short acknowledgment naming
  the words gotten right (`"Nice! You got {matched}."`), then the
  existing `incorrect_response()` + real phonics-sound reinforcement
  (`_play_real_phonics_sounds()`) runs **only for the missed
  word(s)** -- not re-praising the ones already right.

`random_correct_response()` and `_CORRECT_RESPONSES` are unchanged
and still used by the separate decision-0057 "missing letters" bonus
game, which this didn't touch.

## Consequences

One existing test's assertion updated (it counted two
`_CORRECT_RESPONSES` lines for an all-correct two-word family; now
asserts the single combined line instead). One new test added for
the previously-uncovered partial-credit path (one word right, one
missed) confirming the combined ack line, the focused correction for
only the missed word, and that no per-word praise line leaks in.

Full suite: 617 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged pre-existing baseline, no usable SDL video driver in
this dev environment).
