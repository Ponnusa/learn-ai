# 0080 — The re-read offer understands naming the story, and "new"

Date: 2026-10-22
Status: Accepted

## Context

Direct follow-up to decision 0079. A new transcript showed the exact
same pattern as the one that motivated 0079, twice in one session:
asked *"Would you like to read 'The little frog' again, or try
something new?"*, the reply was *"The little frog"* -- the most
natural way a child would say "yes, that one," but containing no
actual yes/no word. Decision 0079 already stopped this from
permanently losing the offer, but it still never actually reread the
story in that exchange -- the reply stayed classified as "unclear"
and fell through to generating something new, only asking again on a
later cycle.

Code review surfaced a mirror-image gap while fixing this: "new" or
"something new" -- the natural way to decline *this specific*
two-choice question -- isn't a generic negative word either (not in
`intent/router.py`'s `_NEGATIVE_WORDS`), so it would also have been
misclassified as "unclear" rather than understood as "no, something
new," asking again on a future cycle when the child had already
clearly answered.

## What shipped

**`voice_loop_demo.py`**: new `_classify_reread_reply(reply,
story_title) -> bool | None`, local to this one offer (not a change to
the general-purpose `intent/router.py`, since "naming the story" and
"new" are specific to this exact question's two-choice phrasing, not
a general yes/no pattern). Checks, in order:
1. Does the reply mention "new"/"different"/"another"/"else"/
   "something else"? → decline.
2. Do all of the story title's own words appear in the reply? →
   reread.
3. Otherwise, fall back to `classify_affirmative()` for a plain yes/no.

Found while writing this: checking `classify_affirmative()` first (the
original plan) let "something new please" match as a yes on the word
"please" alone, before "new" -- the word that actually decides this
question -- was ever considered. The decline-phrase check now runs
first specifically to avoid that.

The call site's `classify_affirmative(reread_reply)` is now
`_classify_reread_reply(reread_reply, most_recent.title)` -- one line
changed, same `True`/`False`/`None` handling from decision 0079
otherwise untouched.

## Consequences

New tests: `_classify_reread_reply()` recognizes the story's own title
as a yes (including with extra words, e.g. "the little frog story");
recognizes "new"/"something new"/"something else" as a no; still
handles plain "yes"/"no" exactly as before; returns `None` for
genuinely unrelated text. One end-to-end integration test: naming the
story accepts the offer on the very first try (not just "doesn't get
permanently lost" like decision 0079 alone guaranteed) -- the offer is
asked exactly once, not repeated.

Full suite: 597 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- This pattern (a specific offer whose natural answers aren't generic
  yes/no words) is handled locally for this one offer only -- the
  word-family offer and word-game offer still rely on plain
  `is_affirmative()`. Not reported as a problem for either; not
  addressed here.
