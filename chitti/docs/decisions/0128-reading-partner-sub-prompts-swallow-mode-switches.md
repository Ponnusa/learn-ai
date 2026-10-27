# 0128 — Reading Partner's own sub-prompts never checked for a mode switch

Date: 2026-10-27

Status: Accepted

## Context

Real-hardware log, right after manually testing decision 0127's
intent-switching fixes: Story Companion -> "I want to practice my
reading." correctly switched into Reading Partner. Then, inside
Reading Partner, the child said "I want to teach you something."
**three times in a row** and never once switched into Teachable-
Friend:

1. First time, in answer to "Would you like to read 'X' again, or try
   something new?" -- swallowed by `_classify_reread_reply()`, which
   has no yes/no/switch signal in that text, so it fell through to
   "not a reread" and Chitti generated a brand new book instead.
2. Second time, in answer to the per-sentence "Would you like me to
   read it to you first?" offer -- `_classify_read_first_offer_reply()`
   (decision 0087) matches the literal word "you" as "yes, read it to
   me" (its own fix for "you read it"), and "teach **you** something"
   contains "you" -- so Chitti modeled the wrong, newly-generated
   story aloud instead of switching.
3. Third time, fed straight into the whole-story read-aloud capture
   (`assess(book.text, spoken_whole, ...)`) -- scored as a badly
   misread sentence ("Let's work on this one: 'A hen sat on a log.'"),
   not recognized as speech at all.

Root cause: `_run_reading_partner()` has several capture points of its
own, each built to answer one SPECIFIC narrow question
(`_classify_reread_reply()`, `_classify_read_first_offer_reply()`) --
and only the "want another one?" capture between books (and the word
game's own capture) ever called `_maybe_switch_mode()` (decision
0127's helper). The two offers above never did. Confirmed directly in
`voice_loop_demo.py`: `_classify_reread_reply()`/
`_classify_read_first_offer_reply()` are called immediately on the
raw capture, with no `_maybe_switch_mode()` check anywhere near them.

## What shipped

`_maybe_switch_mode()` is now checked first at both of these capture
points, exactly the same way the "want another one?" capture already
did it -- if a switch is detected, `next_mode`/`switch_trigger_text`
are set and the mode's own `while True:` loop breaks, same as every
other call site:

- The reread offer ("Would you like to read 'X' again, or try
  something new?") -- checked before `_classify_reread_reply()`.
- The per-sentence "Would you like me to read it to you first?" offer
  -- checked before `_classify_read_first_offer_reply()`, so its own
  "you" heuristic (decision 0087) can no longer misfire on a switch
  phrase that happens to contain the word "you".

The whole-story read-aloud capture is **deliberately left unchecked**
-- that capture's text IS the story being read back, so running
phrase detection on it would be a guaranteed false-positive source
(an existing test already locks this in:
`test_run_reading_partner_never_checks_the_read_aloud_transcript_for_a_switch`).
A child asking to switch mode mid-read-aloud still has to wait for the
next yes/no sub-prompt to say so -- a real, but much smaller and
pre-existing, limitation than the two fixed here, and consistent with
this hardware's push-to-talk-only constraint (decision 0016: no live
interruption is possible anyway).

## Consequences

- A child's genuine mode-switch request, said in reply to either of
  these two offers, now actually switches instead of being silently
  reinterpreted as an answer to a question it was never answering.
- `test_classify_read_first_offer_reply_still_recognizes_plain_yes_and_no()`'s
  own `"let's just chat"` -> `False` case is no longer what actually
  happens at runtime (it now switches to Just Chat before that
  classifier ever runs) -- the unit test for the classifier itself is
  unchanged and still correct in isolation; only the full
  `_run_reading_partner()` flow around it changed.
- `test_run_reading_partner_never_checks_the_read_aloud_transcript_for_a_switch()`'s
  first scripted capture was changed from `"tell me a story"` to
  `"no thanks"` -- with the new offer-level check, `"tell me a
  story"` would (correctly) switch to Story Companion right at the
  offer, before the read-aloud capture the test exists to protect was
  ever reached.

## Not yet done

- The whole-story read-aloud capture itself still can't be
  interrupted by a mode-switch phrase -- out of scope here, same
  reasoning as decision 0127's own rejection of mid-playback
  interruption on this hardware.
- The word game's own per-answer capture and the hint-ladder's
  per-attempt captures weren't audited here -- this fix is scoped to
  the two specific sub-prompts the real log showed swallowing a
  switch request.
