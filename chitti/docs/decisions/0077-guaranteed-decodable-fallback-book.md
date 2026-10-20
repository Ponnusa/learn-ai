# 0077 — A guaranteed-decodable fallback book, ported from Stage A

Date: 2026-10-20
Status: Accepted

## Context

Direct follow-up to decision 0076's own "Not yet done": *"can we get
the character that the child likes like dinosaurs input by the parent
like in the git code that we ported and use that to build a simple
story based on the story input by parent, i mean simple words like
that story but not the same story by llm and should never fail."*

Decision 0076 measured real improvement in LLM book generation's
success rate (roughly 0% to 50-65% for a brand-new profile), but was
explicit that it is **not** a guarantee -- the hardest budget level
can still fail. The phono-storyforge project this whole Reading
Partner mode's deterministic core was ported from
(decodability.py/alignment.py/mastery.py/curriculum.py/planner.py,
all Apache 2.0) has an answer to exactly this already built: its own
provider layer (`app/tutor/book_source.py`'s
`make_llm_book_provider()`) wraps the LLM generator with a fallback to
`eval/book_builder.py`'s deterministic, offline builder whenever the
LLM one raises -- "Stage A" (deterministic) catching for "Stage B"
(LLM) by design, not an afterthought.

## What shipped

**New module `reading/deterministic_book.py`**, ported near-verbatim
from `eval/book_builder.py` (Apache 2.0) onto this package's own
decodability engine and curriculum data (`decodability.py`,
`curriculum.py`) instead of re-importing the reference project's
copies:
- A curated, fixed corpus of ~500 single-syllable decodable words
  spanning the full phonics scope-and-sequence, indexed by every
  grapheme they exercise (including the structural `_blend_`/
  `-s`/`-ed`/... sentinels, same keying `book_generation.py`'s own
  `_grapheme_keys()` already uses).
- `build_deterministic_book(objective, ...)`: picks words exercising
  the target grapheme, one per spaced-review grapheme, and decodable
  filler to reach the target length, with sight-word connectors woven
  in every few words so it reads as text rather than a flashcard
  list. Fully offline, no LLM call, no network -- **cannot** raise
  `BookGenerationError` and cannot produce an undecodable word, by
  construction, not by retrying until it works.
- `interest` (the parent-set "character the child likes," e.g.
  "dinosaurs" -- `ChildProfile.interest`, already existed) flavors
  only the **title** ("Dinosaurs Word Time!"), never the body text.
  Titles aren't decodability-checked anywhere in this package, but
  real thematic vocabulary like "dinosaur" itself is almost never
  decodable at the earliest levels this fallback exists for --
  pretending the body was themed would not be honest, so only the
  title is.
- `source_passage` (the parent's own uploaded exercise, when
  available): its own words that happen to already be decodable at
  the current budget are preferred as filler over the generic corpus
  -- "simple words like that story," a loose thread back to what the
  child was actually just reading, without needing LLM creativity to
  find them.
- Not a narrative -- a short, readable word-practice passage.
  Deliberately not dressed up as more than it is; see the module's own
  docstring.

**`voice_loop_demo.py`**: both `_run_reading_partner()`'s and
`_run_reading_partner_v2()`'s `BookGenerationError` handling now falls
back to `build_deterministic_book(...)` instead of the apology. For
`_run_reading_partner()`, this sits after the existing themed-then-
plain retry sequence (decision 0071) -- only reached if *both* of
those fail. The old apology-and-break code path is now dead in
practice (nothing left can leave `book` unset), so it was removed
rather than kept as unreachable dead code.

## Consequences

New `test_reading_deterministic_book.py` (9 tests): fully decodable
for a fresh profile; fully decodable across **every** grapheme in the
curriculum (`GRAPHEME_INVENTORY`), checked against each one's real
cumulative budget; never raises; pages end with terminal punctuation
(so `sentences.split_into_sentences()` segments it the same as any
other book); titles with the interest when given, generically
without it; prefers decodable words from a source passage; and is
deterministic for the same session index while varying across
different ones.

New integration tests in both `test_voice_loop_demo_intent.py` and
`test_voice_loop_demo_reading_partner_v2.py`: when every LLM attempt
fails, the session falls back to the deterministic builder and
continues normally -- no apology, ever -- confirmed with a scripted-
then-generic-fallback capture function rather than guessing the exact
number of turns the fallback's own (unpredictable, non-narrative)
content would otherwise need.

Full suite: 580 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- `UNTEACHABLE_GRAPHEMES` (ported alongside the rest -- graphemes this
  corpus has no decodable word for at their own introduction budget:
  `ph`, `ng`) is computed but not yet consulted by `planner.py`'s
  `select_objective()` -- the reference project's own experiment loop
  uses it to pre-master such graphemes so the planner never stalls;
  Chitti's planner doesn't currently need this (the LLM path can
  still write around them, and this fallback still produces a full-
  length passage even off-target), but it's available if that
  changes.
- The fallback's word-practice shape (short, punctuated word groups,
  not grammatical sentences) is an honest trade for the guarantee,
  not a temporary placeholder -- a truly narrative guaranteed-safe
  story would need either a much larger hand-curated sentence bank or
  a templating layer neither of which this decision builds.
- `source_passage` reuse only happens in `_run_reading_partner()`'s
  fallback call (where a themed follow-up's source text is already in
  scope) -- `_run_reading_partner_v2()` has no equivalent concept to
  pass through yet, consistent with v2's narrower scope (decision
  0075).
