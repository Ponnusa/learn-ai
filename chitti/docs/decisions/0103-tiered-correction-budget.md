# 0103 — Tiered correction instead of an unbounded or hard-capped loop

Date: 2026-10-24
Status: Accepted

## Context

Follow-up to a "what happens with many sentences" question: decision
0095's per-sentence correction loop fully corrects (hint ladder +
reread + word-meaning check, possibly a word-family detour) every
single flagged sentence in a story, with no cap. For a long story
with many real misses, that's a correspondingly long session and a
correspondingly large number of API calls -- a real, named trade-off,
not a bug.

An outside review, pasted in for a second opinion, proposed: group
misses by phonics skill, fully correct up to two sentences, give a
brief prompt for other high-priority misses, queue the rest for a
later session, and make the numbers configurable for A/B comparison.
Evaluated against the actual code rather than taken at face value:
"update mastery from actual evidence, not loop completion" is already
true today (the whole-story cold-read evidence feeds mastery before
the per-sentence loop even starts; `retry_evidence_accum` feeds in
once after the loop regardless of how far it got) -- no change needed
there. The cross-session "queue for later" and a full config/A-B
system are real scope for a problem not yet observed live; building
them now would be the kind of speculative machinery this project has
otherwise avoided. "Group by phonics skill" already has a concrete,
available signal: the BKT mastery data already tracked per grapheme.

## What shipped

**`voice_loop_demo.py`**, `_run_reading_partner()`'s per-sentence
correction section: `pick_hint_words()` is now called once per
sentence in a pre-pass (`sentence_hint_words: dict[int, list[str]]`),
not recomputed inline -- every flagged sentence is known before any
correction starts. New `_weakest_mastery_for_miscues(miscues,
profile) -> float`: the lowest `p_mastery` among the graphemes a
sentence's own missed words touch, reusing `decodability.decompose()`
to find them; a grapheme never tracked at all counts as `0.0` (never
observed is at least as strong a reason to prioritize it as a
tracked-but-weak one). Flagged sentences are sorted by this (weakest
first); the top `_MAX_FULL_CORRECTIONS` (a plain module constant,
`= 2` -- "a starting value to test, not a proven optimal limit," per
the review's own framing, kept as a constant rather than a config
system since nothing yet justifies the extra surface) get today's
full treatment unchanged. The loop itself still processes sentences
in **story order**, not priority order -- priority only decides which
sentences get which tier, not the sequence the child experiences them
in.

New `_give_brief_callout(hint_words, tts, audio, face, speed)` for
every flagged sentence that didn't make the budget: spotlights each
missed word, says `'Here's a tricky one: "{word}."'`, plays its real
phonics sound (reusing `_play_real_phonics_sounds()`), and moves on --
no hint ladder, no reread, no word-meaning check, no narrowing the
display to one sentence (the whole story stays visible throughout,
unlike a full correction).

## Consequences

Seven new tests: `_weakest_mastery_for_miscues()` (lowest tracked
grapheme wins; an untracked grapheme counts as 0.0; an insertion's
`None` expected word is skipped without crashing), `_give_brief_callout()`
(names each word, spotlights and clears, never emits hint-ladder
text), and one full integration test
(`test_run_reading_partner_tiers_correction_by_weakest_tracked_mastery`)
driving a 3-flagged-sentence story through real masteries and
confirming the two weakest get the full treatment while the third
gets only the brief callout.

Full suite: 649 passed (4 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

No cross-session queue for the brief-callout words -- they're
mentioned once, briefly, and not specifically revisited later (though
ordinary spaced review already applies to their underlying graphemes
via the existing BKT model, same as any other grapheme). No
configurable/A-B-testable budget -- `_MAX_FULL_CORRECTIONS` is a
plain constant, changed the same way every other tuning constant in
this file already is, not exposed as a setting. Both are reasonable
next steps if the 2-sentence budget turns out to be wrong in practice,
not built speculatively now.
