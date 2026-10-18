# 0058 — Hint word selection also skips sight words

Date: 2026-10-19
Status: Accepted

## Context

A fresh live log (pasted by the product owner) showed Chitti hinting
on "the" -- long enough to pass decision 0056's 3-letter minimum, but
"the" is in `curriculum.DEFAULT_SIGHT_WORDS`: meant to be recognized
by memory, not sounded out. "Let's sound it out: th-e" doesn't really
apply to a sight word, and the child's actual replies in that session
("Duh!", "duh") read as genuine annoyance at being asked to sound out
something that trivial. Same bug family as decision 0056's "a," just
caught by a different property (sight-word status, not length) -- a
3-letter length filter alone was never going to catch this.

## What shipped

`reading/hints.py`'s `pick_hint_word()` gained a second exclusion
alongside the existing length check: a miscue whose expected word
(cleaned) is in `curriculum.DEFAULT_SIGHT_WORDS` is skipped, same as
a too-short word -- the search continues to the next real, decodable
miscue rather than giving up or hinting on the sight word.

Scoped to the curriculum's default sight-word list only, not a
per-child custom list -- `pick_hint_word()` only receives the
`AssessmentResult`, not the reading profile, and threading the
profile's own `sight_words` through would be a larger change than
this bug fix calls for.

## Consequences

2 new tests in `test_reading_hints.py`: a sight word is skipped in
favor of a later decodable word in the same read; a read where every
miscue is a sight word returns `None` (same graceful "nothing worth
hinting on this turn" behavior the length filter already established).
Full suite: 447 passed, 1 skipped (pygame unavailable in this dev
environment, pre-existing).

## Not yet done

- Honoring a child's per-profile custom sight words (`ReadingProfile.sight_words`)
  in hint selection, not just the curriculum default list.
