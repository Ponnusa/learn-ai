# 0067 — Sentence-by-sentence reading with a persistent position

Date: 2026-10-20
Status: Accepted

## Context

Last decision in the roadmap the product owner approved alongside
0064-0066. Direct ask: *"when parent gives a big para. can we deivide
into sentecne by sentecne rathter than word, also chiiti should
remember the whole context on where we start and where we are.. so it
doesnt loose the scope."* Confirmed in code: `_run_reading_partner()`
captured and graded an entire passage (`assess(book.text, spoken,
...)`) in one single recording, and nothing about reading position
persisted anywhere -- `ReadingProfile` had no notion of "which
passage, which sentence." Fine for a short, 2-6 sentence generated
book; a real problem for a longer parent-provided paragraph (decision
0052/0063's exercise path): one long recording is harder for a young
child to sustain and harder for STT accuracy, and a session ending
partway through had no way to resume -- it would restart the whole
passage next time.

No new audio architecture was needed: `_capture_and_transcribe()` is
already push-to-talk (record a turn, then transcribe once).
Sentence-by-sentence is the same primitive, just called once per
*sentence* instead of once per whole passage -- a coarser grain, not
a different mechanism.

## What shipped

**New module `reading/sentences.py`**: `split_into_sentences(text)` --
deterministic boundary splitting on `.`/`!`/`?` followed by
whitespace, trimming empties; a passage with no terminal punctuation
at all comes back as one whole sentence, not zero. `passage_key(text)`
-- a stable sha256-based id of the passage's own text, used (not the
book/exercise row id) so a resumed parent-uploaded exercise (same
text across sessions) keeps the same key while a freshly-generated
book (different text every time) always gets a new one, never
confused with an unrelated passage.

**`reading/schema.py`**: `ReadingProfile` gains
`current_passage_key: str | None` and `current_sentence_index: int`,
both reset to None/0 once a passage finishes -- position memory only
matters while something is actually in progress.

**`storage/migrations.py` / `reading/repository.py`**: the two new
columns via `_ensure_column()` (same idempotent-ALTER-TABLE precedent
as `child_profiles`' own added columns), persisted/loaded through
`ReadingRepository.save()`/`get_or_create()` exactly like every other
profile field.

**`reading/alignment.py`**: `merge_assessments(results) ->
AssessmentResult` -- combines one `AssessmentResult` per sentence into
a single whole-passage result (summed counts, accuracy/wcpm recomputed
from the summed totals, concatenated miscues/correct_words/grapheme
evidence). This is what lets `build_reading_feedback()` and the
post-read activities (comprehension questions, word game) keep working
against one `AssessmentResult`, unaware reading happened sentence by
sentence underneath.

**`voice_loop_demo.py`**: `_run_reading_partner()`'s read-aloud step
now loops over `split_into_sentences(book.text)` instead of one
capture of the whole thing. Before the loop, checks whether
`profile.current_passage_key` matches this passage's `passage_key()`
and `current_sentence_index` is short of the end -- if so, resumes
from there with a spoken "Let's pick up where we left off!" cue;
otherwise starts at 0 and claims this passage's key. Per sentence: the
teleprompter shows just that one sentence (decision 0053's existing
rendering, just given one sentence's text instead of the whole book);
the existing hint-and-retry ladder (decisions 0052/0065) and mastery
update (decision 0051) run scoped to that sentence's own
`AssessmentResult` -- strictly finer-grained, not a different
algorithm; `current_sentence_index` and the whole profile are
persisted after **every** sentence, not just at the end, so an
interrupted session loses nothing. Once every sentence is done,
position resets to None/0, the per-sentence assessments are merged via
`merge_assessments()`, and the rest of the turn (feedback, comprehension
questions, word game, "want another one?") runs exactly as before
against that merged result.

## Consequences

New `test_reading_sentences.py`: `split_into_sentences()` on a multi-
sentence paragraph, a single sentence, no terminal punctuation at all,
and blank/empty input; `passage_key()` stability for the same text and
difference for different text.

New `merge_assessments()` tests in `test_reading_alignment.py`:
summed totals/accuracy/wcpm match what one whole-passage `assess()`
call would have produced; miscues and correct_words combine in order;
grapheme evidence accumulates across every sentence, not just the last.

New tests in `test_reading_repository.py`: a fresh profile has no
passage in progress; `current_passage_key`/`current_sentence_index`
round-trip through `save()`/`get_or_create()`; resetting back to
None/0 round-trips correctly too (not the string `"None"` or another
truthy placeholder).

New tests in `test_voice_loop_demo_intent.py`:
`..._shows_and_captures_one_sentence_at_a_time` (each sentence shown
and captured on its own; position resets once the passage finishes
clean) and `..._resumes_mid_passage_after_an_interrupted_session` --
the plan's own required smoke test: a session that raises mid-capture
on sentence 2 of 3 persists `current_sentence_index == 1`; a second,
separate `_run_reading_partner()` call with the same regenerated
passage text (same `passage_key()`) resumes at sentence 2, speaking
the resume cue, never re-showing or re-asking sentence 1.

Two pre-existing tests used a two-sentence generated book with a
single whole-passage capture (`"a cat sat a cat ran"`); updated to one
capture per sentence (`"a cat sat"`, `"a cat ran"`), and one teleprompter
assertion updated from the whole two-sentence list to the first
sentence alone.

Full suite: 519 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

This was the last decision in the approved 0064-0067 roadmap. Nothing
from that roadmap remains open. Possible future follow-ups, not
requested:
- `split_into_sentences()` has no abbreviation handling (e.g. "Mr.");
  fine for this product's own simple, short generated/assigned
  content, but would mis-split a passage that used one.
- A parent-uploaded exercise is still marked consumed as soon as it's
  *started* (decision 0052's existing behavior, unchanged here), not
  once it's actually finished -- an interrupted exercise resumes via
  position memory on the same exercise object in memory, but a brand
  new process picking a child back up mid-exercise after a restart
  would need the exercise to still be fetchable, which this decision
  didn't change.
