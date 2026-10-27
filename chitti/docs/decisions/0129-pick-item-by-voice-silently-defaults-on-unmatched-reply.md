# 0129 — Story/lullaby picker silently defaults when the reply doesn't name any title

Date: 2026-10-27

Status: Accepted

## Context

Real-hardware log: Chitti asks "I have 2 stories: Piki-siilin omena,
The Little Bear Who Lost His Roar. Which one would you like?" The
child answers "I want to read a story" -- not naming either title.
Chitti immediately launches into reading "Piki-siilin omena" with no
acknowledgment at all that the reply didn't answer the question it
just asked. From the child's side this reads as Chitti not listening.

Confirmed directly in `_pick_item_by_voice()`/`_resolve_spoken_choice()`
(`voice_loop_demo.py`): when the captured text is non-empty but
doesn't match a title (substring), an ordinal word, or a fuzzy match
(cutoff 0.4), it silently falls through to `return items[0]` -- no
spoken acknowledgment. Contrast this with the *other* fallback two
lines below it, for when nothing was heard at all: that one DOES
speak "Sorry, I didn't catch that -- let's go with the first one."
before defaulting. A real, specific answer ("I want to read a story")
that simply didn't address the question got treated identically to
dead silence, and worse, silently.

## What shipped

Split the matching logic out of `_resolve_spoken_choice()` into a new
`_match_spoken_choice(spoken, items) -> int | None`, which returns
`None` instead of guessing when nothing actually matched.
`_resolve_spoken_choice()` keeps its old signature/behavior (always
returns an item) for its own existing callers/tests -- it's now a
thin wrapper (`items[index if index is not None else 0]`).

`_pick_item_by_voice()` now calls `_match_spoken_choice()` directly:
a real match returns immediately as before; no match (but the child
DID say something) now speaks an explicit acknowledgment before
defaulting -- `'I didn't quite catch which one you meant -- let's
start with "{first title}"!'` -- the same spirit as the existing
"didn't catch that" line for the empty-reply case, just worded for
"heard you, but not which one."

## Consequences

- A reply that doesn't name any offered title is now always
  acknowledged out loud before Chitti picks one for the child,
  whether nothing was heard or something unrelated was said.
- `_resolve_spoken_choice()`'s own existing tests are unchanged and
  still pass -- its behavior from the outside didn't change, only
  its internals.

## Not yet done

- Still defaults to the first item rather than re-asking -- a second
  spoken retry loop (ask again, up to once) was considered but not
  built here; this fix is scoped to making the silent case match the
  existing "didn't catch that" case, not changing the retry policy
  itself.
