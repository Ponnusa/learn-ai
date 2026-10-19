# 0061 — is_affirmative() strips punctuation before matching

Date: 2026-10-19
Status: Accepted

## Context

An external review of a real Pi log (building on decisions 0052-0060)
raised several points about Reading Partner's interaction design.
Verifying those against the actual code surfaced a different, higher-
impact bug not on the review's own list: the log shows Chitti offering
the post-reading word game ("Ready to play?"), the child answering
**"Yes."**, and the session jumping straight to "want another one?"
with zero game rounds in between -- the word game was silently
skipped despite a clear yes.

Root cause: `intent/router.py`'s `is_affirmative()` splits the
transcript on whitespace (`text.lower().split()`) and matches each
token against `_AFFIRMATIVE_WORDS`/`_NEGATIVE_WORDS` *verbatim* --
never stripping punctuation first. Whisper commonly appends a period
to a short utterance ("Yes."), so the token `"yes."` never equals
`"yes"` in the set, falls through the whole loop, and hits the
function's safer-default `return False`. This isn't scoped to the
word game -- `is_affirmative()` is also decision 0046's mode-switch
confirmation gate (`_confirm_switch()`), so the same bug could
silently mis-read a genuine "yes" as a decline there too, any time
Whisper's output included trailing punctuation.

## What shipped

`is_affirmative()` now strips each word of anything that isn't a
letter/digit/apostrophe (`re.sub(r"[^\w']", "", word)`) before
checking it against either word set. Kept self-contained in
`intent/router.py` (a small inline regex) rather than importing
`reading/decodability.py`'s `clean_word()` -- this module has no
dependency on the `reading/` package today and introducing one just
for this would be a worse trade than four extra characters of regex.

## Consequences

1 new test (`test_is_affirmative_strips_trailing_punctuation`):
`"Yes."` → `True`, `"No."` → `False`, `"Sure!"` → `True`, confirming
the exact failure mode from the log is fixed. Full suite: 462 passed,
1 skipped (pygame unavailable in this dev environment, pre-existing).

## Not yet done

This was found while reviewing an external critique of Reading
Partner's broader interaction design (comprehension-answer handling
giving away answers immediately, hint-ladder wording, latency) --
those are tracked separately, not fixed in this decision.
