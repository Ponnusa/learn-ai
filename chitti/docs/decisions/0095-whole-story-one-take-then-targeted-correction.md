# 0095 — Read the whole story once, then only fix what was missed

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback: *"after similar words, the system got lost of the
context, i think it sould aks the child to read the entire story and
then correct him rather than one sentence by one sentence. first it
should get him to speak the whole story, mark all mistakes and only
make him read those words and sentence where he made mistake not
all. also when reading thhose simlar words, plz higjtlihst those
when chitti says the word. u should remember all the issues for the
story, dont get into loop or become undreidcatble.. complte eontext
must be remembered until the end of the story"*

Decision 0067's per-sentence capture loop called `assess()` once per
sentence and advanced through every sentence regardless of whether
it was read correctly -- a clean sentence still got its own capture
turn, just with no hint ladder afterward. For a short book this is
barely noticeable; the report here is that something about the
word-family detour (decision 0066) leaves the read-aloud flow
feeling like it "lost context" afterward, and the requested fix is a
different shape entirely: one whole-story read, one remembered list
of every real miss, then only the flagged sentences get worked on.

## What shipped

**`reading/alignment.py`**: new `miscues_by_sentence(sentences,
miscues) -> list[list[Miscue]]`. Buckets the miscues from one
whole-passage `assess()` call by which sentence each one's
word-token `position` actually falls in, using cumulative
`tokenize(sentence)` lengths as boundaries. Relies on
`split_into_sentences()` never dropping or reordering words, so the
concatenated per-sentence tokens exactly reproduce the token stream
`assess()` worked from. `merge_assessments()` (decision 0067) is left
in place -- independently tested and still reasonable -- but is no
longer called by v1; nothing currently uses it.

**`voice_loop_demo.py`**, `_run_reading_partner()`'s per-book loop:
replaced the old resume-then-per-sentence-capture-and-correct loop
with:

1. Show the whole story (decision 0093), ask the session-wide "read
   it to you first?" question (decision 0094) if not already
   answered this call, model the whole story in one continuous
   read-through if yes, then ask for **one** whole-story read-aloud
   capture -- not one per sentence.
2. Grade it once (`assess(book.text, spoken_whole, ...)`), feed the
   resulting `grapheme_evidence` into mastery immediately, and bucket
   its miscues by sentence via `miscues_by_sentence()`.
3. Loop over every sentence; `pick_hint_words()` fed a minimal
   stand-in `AssessmentResult` built from that sentence's own miscue
   bucket. A sentence with no miscues is **skipped entirely** -- no
   reread, no re-ask, nothing spoken for it at all. A flagged
   sentence gets the unchanged hint ladder, reread, and word-meaning
   check, narrowed to just that one sentence on screen, then widened
   back to the whole story once its correction is done.
4. Hint-ladder retry evidence (every stage before the last, same
   decision-0065 distinction as before) accumulates into
   `retry_evidence_accum` across every flagged sentence, instead of
   being fed per-sentence -- "remember all the issues for the story"
   means this evidence must survive the whole correction pass, not
   just one sentence's worth. Fed into mastery once, after the loop,
   **before** `reading_repo.save(profile)` -- found live while
   building this: the save used to run first, so the retry update
   never actually persisted.

Decision 0067's per-sentence resume fields
(`current_passage_key`/`current_sentence_index` on `ReadingProfile`)
are no longer read or written by v1 -- a one-shot whole-story capture
has no meaningful mid-passage point to resume from any more. The
columns themselves are untouched (not a migration), just unused by
this caller now. `_run_reading_partner_v2()` is untouched, same as
every decision in this series since 0084.

**`device/screen_face.py`**: `_draw_word_grid()` gained an optional
`highlight` parameter -- the matching word's box is drawn in a
distinct color (`_WORD_GRID_HIGHLIGHT_BOX_COLOR`, red, same accent
as the hint spotlight) with a thicker border, while every other
word's box renders unchanged. New `set_word_grid_highlight(word)` /
`_get_word_grid_highlight()` on `ScreenFaceDeviceController`,
independent state from `set_word_grid()` itself (the grid's own
words don't change, just which one is picked out), read by the
render loop alongside the grid. `_run_word_family_practice()`'s
modeling loop (decision 0094's `read_first=True` path) now calls
`face.set_word_grid_highlight(family_word)` right before speaking
each word, and clears it once modeling is done -- so the word
Chitti is actually saying is visually picked out of the grid instead
of the whole grid just sitting there static throughout.

## Consequences

Two real bugs found and fixed while rebuilding this flow (not just
scripted-reply mismatches):
- Retry evidence was being merged back into `assessment.grapheme_evidence`
  -- a dict already consumed by the first `update_from_evidence()`
  call by the time the hint ladder even starts, so every retry
  silently vanished. Mastery opportunities from a corrected retry
  never counted. Fixed by merging into `retry_evidence_accum` and
  feeding it through its own `update_from_evidence()` call instead.
- `reading_repo.save(profile)` ran before that second
  `update_from_evidence()` call, so even once the evidence was
  flowing to the right place, the retry's mastery update was never
  persisted. Fixed by moving the save to after.

Ten tests updated for the new one-capture shape (scripted replies
merged from N per-sentence captures into one whole-story capture;
display-state assertions updated for "whole story -> one flagged
sentence -> whole story" instead of "shown once, never touched
again"); one test
(`test_run_reading_partner_resumes_mid_passage_after_an_interrupted_session`)
deleted outright, since its entire subject -- decision 0067's
mid-passage resume -- no longer exists for v1. One new test added
directly for `_run_word_family_practice()`'s highlight behavior
(nothing previously exercised the `read_first=True` modeling path
for word families at all).

Full suite: 616 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged pre-existing baseline, no usable SDL video driver in
this dev environment).

## Not yet done

The original "lost of context" bug report may have been this same
per-sentence-capture friction all along, or something else entirely
-- there's no hardware transcript confirming which. If it resurfaces
after this ships, it's a different, still-open bug, not something
this decision can be assumed to have silently fixed.
