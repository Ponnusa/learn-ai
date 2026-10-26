# 0117 — Vary which thinking filler plays, instead of always the same one first

Date: 2026-10-26
Status: Accepted

## Context

Direct feedback from a real session log: "we have too many fillers -
may be only one filler is needed while thinking and we can rotate
with many fillers so we dont need to repeat the same word and child
doesnt get bored." Confirmed against the code:
`_speak_while_thinking()` (decision 0050, spoken while a real LLM
call runs in the background) always walked `_THINKING_FILLERS` in
the exact same fixed order on every single call -- "Hmm, let me
think about that..." first, every time. Most individual LLM calls
only need one filler before finishing, so in practice the child was
hearing that one exact opening line over and over across a session
with many LLM waits (book generation, comprehension questions, word
reactions, ...) -- not "too many at once," but the same one too
often across the whole session.

## What shipped

`_THINKING_FILLERS` expanded from 3 to 6 lines. `_speak_while_thinking()`
now picks a random subset/order each call
(`random.sample(_THINKING_FILLERS, min(_MAX_FILLERS_PER_WAIT, len(_THINKING_FILLERS)))`)
instead of walking the list from the start -- the common case (a
fast call, one filler needed) now draws a different line each time
instead of always the same one. `_MAX_FILLERS_PER_WAIT = 3` keeps the
original cap on how many play during any single genuinely-long wait
(same number decision 0050 originally used, back when the whole pool
was that size) -- a long tail of silence for an unusually slow call
is still preferable to droning through everything available.

## Consequences

Two existing tests updated for randomized order (checking pool
membership/counts instead of an exact fixed sequence). One new test,
`test_speak_while_thinking_varies_which_filler_comes_first()`, calls
the function 20 times and confirms more than one distinct filler
shows up first across those calls -- the actual property this
decision changed. Full suite: 721 passed (the same handful of
pre-existing, unrelated `test_screen_face_rendering.py` failures --
no usable SDL video driver in this dev environment).

## Not yet done

The word game's own phonics-breakdown reaction (decision 0112, kept
deliberately when decision 0116 removed the hint ladder's phonics
teaching) was raised again in the same conversation as this decision
-- not changed here, pending the user's answer on whether to also
drop it now.
