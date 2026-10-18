# 0056 — Hint word selection skips trivially short words

Date: 2026-10-18
Status: Accepted

## Context

Found live: Chitti selected "a" as the hint-and-retry target and said
"that word starts with the 'a' sound" -- nonsensical for a word that
*is* the sound, nothing to graduate into sounding out. `pick_hint_word()`
had no length check at all; it just returned the first substitution/
omission in reading order, regardless of how trivial the word was.

Related, separate observation from the same session, not fixed here:
the child's actual read-aloud that turn ("That's what I'm trying to
tell you. Let's see what it says...") bore no resemblance to the
story on screen at all -- a near-total mismatch, not a normal misread.
Hinting on *any* single word from a read that unrelated is somewhat
arbitrary no matter which word gets picked; this fix narrows one real
bug (trivial words as hint targets) without attempting to detect "this
isn't a genuine attempt at the passage at all," which is a different,
harder problem.

## What shipped

`reading/hints.py`'s `pick_hint_word()` now skips any miscue whose
expected word is shorter than `_MIN_HINT_WORD_LENGTH = 3` letters,
continuing to scan for the next real miscue instead of returning the
trivial one. 3 is deliberately the length of this curriculum's own
shortest real phonics targets (CVC words like "cat"/"sat"/"mat") --
short enough to keep those as valid hint targets, long enough to skip
one- and two-letter function words ("a", "I", "is") that have nothing
to graduate a hint on. If every miscue in a read is too short, the
turn simply has no hint this time (returns `None`, same as a clean
read) rather than forcing one.

## Consequences

2 new tests in `test_reading_hints.py`: a trivial first miscue is
skipped in favor of a later, substantial one; a read where every
miscue is too short returns `None`. Full suite: 428 passed, 1 skipped
(pygame unavailable in this dev environment, pre-existing).

## Not yet done

- Detecting a read that bears no resemblance to the assigned passage
  at all (vs. an ordinary misread) -- flagged above, not attempted.
