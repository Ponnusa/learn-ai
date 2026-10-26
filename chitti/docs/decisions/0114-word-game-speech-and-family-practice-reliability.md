# 0114 — Word game stops narrating letters and stops re-laying-out the story; word family stops losing words to Whisper

Date: 2026-10-26
Status: Accepted

## Context

Direct feedback from a real session transcript, four separate points:

1. The word game's intro and its follow-up prompt both explained the
   task ("tell me what letters are missing and say the whole word"),
   and the follow-up additionally spelled the blanked letters out loud
   ("M, blank, S, T") -- redundant with the intro, and (confirmed from
   an earlier log) occasionally spoke a stray literal "." when the
   target word happened to end a sentence. The explicit ask: Chitti
   should just point at the (already on-screen, already red-
   highlighted) blanks and ask for a read -- no narrated spelling.
2. Word-family practice's grid: "it was not reading all words -- it
   missed many words, only one word was spoken." Traced to decision
   0102's combined-utterance modeling (all 4 family words synthesized
   as one TTS clip, re-transcribed via Whisper to sync the grid
   highlight word-by-word) -- the same Whisper merge/miscount failure
   that produced a garbled "Samus" highlight for "Sam is sad." earlier
   this session, but worse here: a short, fast string of unrelated
   rhyming words (e.g. "hat. bat. cat. mat.") is exactly the case
   Whisper's own re-transcription struggles with most.
3. ("rid" flagged as a miscue the child didn't actually make --
   discussed, not a code bug: the transcript the assessment saw really
   did read "Read" for "rid," an STT mis-hearing with no way for the
   code to distinguish from a real miss. No change made for this.)
4. Separately, while implementing #1: confirmed the same real session
   showed the story's own on-screen layout visibly change shape right
   after the word game ran (5 lines collapsing to 4, two sentences
   merging onto one line) for `story_library.py`'s own `"it-is-dim"`
   story, whose last *page* happens to bundle two sentences
   (`'Sam is sad. That is it.'`). Root cause: `_run_word_game()`
   (decision 0112) blanked and later restored `book.pages`, while the
   rest of the session displays `sentences` (`split_into_sentences(book.text)`)
   -- a different split of the same text whenever a page and a
   sentence don't line up 1:1. Flagged as a theoretical risk when
   decision 0112 shipped and dismissed as rare; this log proved it
   isn't.

## What shipped

**`voice_loop_demo.py`'s `_run_word_game()`**: now takes `sentences`
(the exact list already on screen) instead of operating on
`book.pages` -- blanking, highlighting, and restoring all use it, so
finishing the game can never change the story's own displayed shape.
The post-accept prompt no longer spells anything out: `"{They
are/It is} highlighted in red in the story -- go ahead and read
{them/it} for me."` -- the intro (unchanged) already explained the
task once.

**`reading/word_game.py`**: `spell_out_blanked()` removed entirely
(its only caller was the prompt above).

**`_run_word_family_practice()`**: dropped decision 0102's combined-
utterance branch; always uses the simple per-word loop now (one TTS
call per word, highlight trivially synced to that one call, no
Whisper re-transcription involved at all) regardless of what the STT
backend supports. Costs one extra TTS round trip per word instead of
one combined call, in exchange for actually being reliable.

## Consequences

Rewrote the word-game intro/prompt test coverage implicitly (no
assertions referenced the removed spelling text) and added
`test_run_word_game_matches_the_sentence_split_already_on_screen()`,
reproducing the exact real-story shape (one exercise *line* holding
two sentences) and asserting the displayed/blanked/restored shape
never changes. Renamed and rewrote
`test_word_family_practice_combines_words_into_one_utterance_when_timestamps_available`
to `..._models_each_word_with_its_own_tts_call_even_with_timestamps`,
asserting the per-word calls happen even when the STT fake supports
timestamps. Removed `test_spell_out_blanked_is_speakable` (dead
code's own test).

Full suite: 725 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

Sentence modeling's own occasional single-word Whisper-merge issue
(the "Samus" case, decision 0098's `align_timings_to_expected_text()`
own documented fallback) is unchanged -- lower-impact there (one
word's highlight silently wrong/skipped within an otherwise-normal
sentence read, not most of a short utterance going dark) and not
addressed by this decision. The STT-mis-hearing-as-false-miscue
discussion (point 3 above) has no code change -- flagged as an
inherent limitation, not something fixed here.
