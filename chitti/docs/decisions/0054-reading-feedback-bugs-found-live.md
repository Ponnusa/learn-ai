# 0054 — Reading Partner: two feedback bugs found live

Date: 2026-10-18
Status: Accepted

## Context

A real Pi session (pasted log) surfaced two separate problems with
the end-of-book feedback turn, plus a product question worth
answering explicitly rather than just in chat: Reading Partner has no
comprehension-check feature at all. It was never built -- decision
0051's "Not yet done" section already named "comprehension questions
and a parent progress report" as a separate, larger follow-up, and
nothing since has changed that. The feedback a child hears after a
book is purely **decoding/phonics mastery feedback** (which letter-
sounds they're getting good at), never a check of whether they
understood the story. Worth stating plainly here since it's an easy
thing to expect and not get.

The two real bugs, both in the code this session already shipped:

1. **Internal tracking keys spoken aloud, unbounded in count.** The
   real log: *"You're getting really good at the 'a', 'l', 'i', 't',
   'e', '_blend_', 'b', 'u', 'n', 'y', 'o', 'p', 's', '-s', 'th', 'd',
   'ee' and '-es' sounds!"* -- 18 items in one breath, including
   `alignment.py`'s own internal bookkeeping sentinels (`_blend_` for
   "any adjacent consonant blend was read correctly", `-s`/`-es` for
   suffix-ending tracking) that were never meant to be read aloud as
   if they were phonics sounds. This happens because a near-perfect
   first read of a book can cross the BKT mastery threshold for most
   of its graphemes in one session at once, and `feedback.py`'s
   `_spoken_list()` had no filtering and no cap.
2. **No spoken cue that Chitti was waiting on the child.** After the
   feedback line, the mode silently started listening again with
   nothing said in between -- this is exactly what decision 0051's own
   original plan called for ("ask 'want to try another one?' and
   capture that short reply"), but the line was never actually added
   to the shipped code. From the log: feedback plays, then silence,
   then "Press Enter to start talking..." with no idea what's being
   asked.

## What shipped

**`reading/feedback.py`**: `delta.newly_mastered` is filtered to
`g.isalpha()` before being spoken -- every real grapheme key
(`"sh"`, `"ee"`, single letters) is plain letters; every sentinel
(`"_blend_"`, `"-s"`, `"-ed"`, `"-es"`, `"-ing"`) contains `_` or `-`,
so one simple predicate separates them without hardcoding each
sentinel name. If a session only crossed sentinel thresholds, the
whole "sounds" sentence is skipped rather than saying nothing useful.
`_spoken_list()` also caps itself at 3 named sounds
(`_MAX_SPOKEN_SOUNDS`), appending "and more" when there were more --
naming a dozen-plus sounds in one unbroken sentence doesn't read as
praise, it reads as a wall of words.

**`voice_loop_demo.py`**'s `_run_reading_partner()`: a spoken prompt
("Want to try another one, or would you like to do something else?")
now plays between the feedback line and the "what next" capture --
the actual missing line from decision 0051's own plan.

## Consequences

4 new tests in `test_reading_feedback.py` (sentinel keys never
spoken, a sentinel-only mastery delta adds nothing, the 3-item cap
with "and more"), plus one assertion added to an existing end-to-end
`test_voice_loop_demo_intent.py` test confirming the new prompt is
actually spoken. No existing test needed to change beyond that one
assertion -- the new prompt is appended after every index earlier
tests check exactly, so nothing shifted. Full suite: 424 passed, 1
skipped (pygame unavailable in this dev environment, pre-existing).

## Not yet done

- Reading comprehension checking (questions about the story, not just
  decoding accuracy) and a parent-facing progress report -- both
  still open, larger follow-ups, unaffected by this fix.
