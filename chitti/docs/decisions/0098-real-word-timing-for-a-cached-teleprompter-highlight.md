# 0098 — Real word timing, cached per sentence, for Chitti's own reads

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback: *"just like some teleprompter github code i ave
earlier provided, these story is fixed and needs one llm call to get
the word and timer correct for the telepromot kind of experience.,
and we can store this info for the story or needs for the story only
once right.. if child makes a mistake on a sentence we can reuse the
same while reading single sentence and no need for a new llm call..
then why not do it"*

Decision 0088 removed the previous word-by-word teleprompter highlight
entirely, because it tracked elapsed wall-clock time against a
*simulated* reading pace (a WPM estimate), not the real audio -- that
desynced badly on real hardware and was the actual reason it was
dropped, not its cost. Clarified with the product owner before
building anything: this is about highlighting words as **Chitti**
speaks them (the modeling steps), not the child's own read -- the
latter would need live alignment against the child's in-progress
speech, which nothing here solves.

The "one call, cache it, reuse it" framing turned out to describe
exactly the "book-karaoke" GitHub technique already evaluated and
reported back in decision 0088: synthesize the fixed text once, then
run that *same* audio through Whisper with word-level timestamps to
recover real, audio-grounded word boundaries -- not a second LLM
text-generation call, a Whisper transcription call against Chitti's
own TTS output. Since the text is fixed, that result can be cached
and reused for any later playback of the identical text at the
identical speed, which is precisely the "child makes a mistake on a
sentence, reuse it for that single sentence" scenario described --
`_run_reading_partner()` already models the same sentence twice in
one call at the same speed: once in the up-front whole-story
read-through (decision 0094), again just before that sentence's own
reread after a hint-ladder correction (decision 0074).

## What shipped

**`reading/word_timing.py`** (new): `WordTiming` dataclass
(`word`/`start`/`end`); `parse_word_timings()` for Whisper's
`verbose_json` word-timestamp format (skips malformed entries rather
than raising); `pcm_to_wav_bytes()` wrapping OpenAITTSBackend's own
headerless raw-PCM output in a real WAV container, since Whisper's
endpoint needs an actual audio file to parse.

**`voice/stt_openai.py`**: `OpenAIWhisperBackend` gains
`transcribe_with_word_timestamps(pcm_audio) -> list[WordTiming]` --
requests `verbose_json` + `timestamp_granularities[]=word` instead of
plain text. Not added to the `SpeechRecognitionBackend` ABC -- an
additive capability callers check for with `getattr`/`hasattr`, same
precedent as every other "degrade gracefully if absent" feature in
this codebase, so no other backend or test fake needs to implement it.

**`device/screen_face.py`**: `_draw_reading_lines_static()` takes an
optional `highlight_word` -- every occurrence of that one word
renders in a distinct color (word-by-word `font.render()` calls with
measured spacing, replacing the old single per-line blit), while the
rest of the text is untouched. The text itself never moves or
scrolls -- only a word's color changes -- so this stays immune to
decision 0088's actual reason for removal. New
`set_reading_text_highlight(word)` / `_get_reading_text_highlight()`
on `ScreenFaceDeviceController`, independent of `set_reading_text()`
itself, read by the render loop each frame.

**`voice_loop_demo.py`**: new `_speak_with_word_highlight(tts, audio,
face, stt, text, speed, cache)`. On a cache miss: synthesizes once,
calls `transcribe_with_word_timestamps()` if the backend supports it
(wrapped in try/except -- a failed lookup logs and falls back to a
plain, unhighlighted `_speak()`, never breaks the read-aloud),
caches `(audio_bytes, timings)` keyed by `(text, speed)`. On a cache
hit: reuses both, no fresh TTS call and no fresh Whisper call. Plays
the audio as a background task while ticking through the cached
timings in real time, updating the highlight to match; always clears
the highlight afterward via `finally`. A new
`modeled_word_timings_cache: dict` is declared once per call to
`_run_reading_partner()`, same per-call scoping as
`read_first_preference` (decision 0094). Both places that model the
same sentence at the same speed (the up-front whole-story
read-through, and a flagged sentence's own pre-reread modeling) now
call this instead of plain `_speak()`.

## Update: highlighting scoped to the sentence actually being spoken

Found live, immediately after shipping: reading "Sam and the Cat"
("Sam has a cat. The cat can nap. Sam can nap. Sam and the cat nap in
the sun."), highlighting "Sam" while modeling sentence 3 ("Sam can
nap.") also lit up "Sam" in sentence 1 and sentence 4 -- every
sentence containing that word, not just the one being spoken. Not an
LLM data problem (first guess) -- the whole story is shown on screen
at once (decision 0093), and `_draw_reading_lines_static()` matched
the highlighted word against every visible line with no sentence
context at all, so a word repeated anywhere in the story lit up
everywhere it appeared.

Fixed by threading the sentence's own index through end to end:
`_speak_with_word_highlight()` takes a required `sentence_index`
argument (both call sites already have it -- `enumerate(sentences)`
in the up-front modeling loop, the existing `sentence_index` loop
variable in the per-sentence correction loop) and passes it straight
to `set_reading_text_highlight(word, sentence_index)`.
`ScreenFaceDeviceController` stores the highlight as `(sentence_index,
word)` instead of a bare word. The render loop now tags each wrapped
display line with the index of the original sentence ("page") it
came from (`[(page_index, line), ...]` instead of `[line, ...]`), and
`_draw_reading_lines_static()` only highlights a matching word on
lines whose `sentence_index` matches the target -- every other
sentence's occurrence of the same word renders in the plain color,
unaffected.

Two tests added for this directly: one on `_speak_with_word_highlight()`
confirming `sentence_index` passes straight through unchanged to the
face; one reproducing this story's exact setup is implicit in the
first, since the scoping logic has no special-casing by word.

## Update: trusting Whisper's timing, not its re-transcribed word text

Found live, immediately after the sentence-scoping fix above: in
"Sam and the Cat," "nap" -- appearing in 3 of the 4 sentences -- never
highlighted at all, while other words in the same sentences did.
Whisper's `transcribe_with_word_timestamps()` re-transcribes
Chitti's own short, synthesized audio from scratch; a short, clipped,
closed-syllable word like "nap" is exactly the kind of thing Whisper
can mis-hear or drop at an utterance's edge, even though we already
know with certainty what text was actually spoken -- we asked the
TTS backend to say it. There was never a good reason to trust
Whisper's own transcribed word *text* over that; only its *timing*
is genuinely unknown in advance.

New `align_timings_to_expected_text(expected_text, timings)` in
`reading/word_timing.py`: substitutes each timing's word with the
corresponding word from `expected_text`, matched by position,
keeping Whisper's own start/end untouched. Only substitutes when the
word counts match exactly -- if Whisper split, merged, or dropped a
word, position no longer lines up reliably, so it falls back to
Whisper's own words unchanged rather than guessing a worse mapping.
Called in `_speak_with_word_highlight()` right after the timestamp
lookup, before caching -- the cache stores the already-corrected
timings, so a cache hit doesn't need to re-align anything.

Two new tests: the substitution replacing a wrong/mis-heard word by
position while keeping Whisper's own timing, and the count-mismatch
fallback leaving Whisper's words untouched.

## Update: the narrowed single-sentence display has its own page 0

Found live, from a full session log: during a flagged sentence's own
correction, the "Let's work on this one: ..." cue read the sentence
aloud but never highlighted anything, and the later "I'll read it
for you first. Listen:" reread-model logged `reading text highlight:
... (sentence 3)` calls that never actually appeared on screen
either. Two separate problems:

1. The attention cue spoke the WHOLE flagged sentence embedded
   inside one longer phrase (`'Let\'s work on this one: "{sentence}"'`)
   via plain `_speak()` -- never through the highlighting path at
   all. Split into an unhighlighted intro ("Let's work on this
   one:") followed by the sentence itself spoken through
   `_speak_with_word_highlight()`.

2. The real bug: `face.set_reading_text([sentence], ...)` (right
   before the attention cue) narrows the display to a ONE-ITEM page
   list for the entire rest of the correction block -- it's the
   only page on screen until the block ends and
   `face.set_reading_text(sentences, ...)` widens it back out. Both
   calls to `_speak_with_word_highlight()` inside that block were
   still passing the sentence's ORIGINAL index into the whole story
   (e.g. `3`), which the render loop's `(page_index, line)` pairs
   could never match -- there was only ever a page `0` to check
   against. The `reading text highlight: ... (sentence 3)` log lines
   were real, but nothing on screen could ever match them, so
   nothing actually lit up. Both call sites now pass `0`, matching
   the narrowed display, with a comment explaining why.

One new integration-level test
(`test_run_reading_partner_highlight_uses_the_narrowed_display_page_not_the_story_index`)
drives a 2-sentence story where the SECOND sentence (story index 1)
is the one flagged, and asserts every recorded highlight call uses
page index 0, not 1 -- this is exactly the shape that would have
caught the bug (a flagged sentence at index 0 wouldn't have, since 0
looks identical whether buggy or fixed by coincidence).

## Update: position-based matching, and holding the last word

Found live, two more bugs from the same real-hardware session:

1. **The last word never highlighted at all.** Every other word's
   highlight persists on screen until the loop advances to the NEXT
   word's own start time, which overwrites it. The LAST word has no
   "next" to wait for -- the old code set its highlight and then fell
   straight through to the `finally` block's clear, with no delay in
   between at all. The highlight was real (the log line fired) but
   had no time to actually render before being cleared again. Fixed
   by holding the last word for its own remaining duration
   (`last_timing.end`) before the function returns, exactly mirroring
   how every other word is naturally held by the next one's start.

2. **A word repeated within one sentence highlighted all of its own
   occurrences at once.** "Pat and the pup run and run." has "and"
   twice; the moment the FIRST "and" was spoken, matching by
   normalized word TEXT (`_normalize_word`) lit up both -- the exact
   same ambiguity as the earlier cross-sentence "Sam" bug, just
   within one sentence instead of across several. Fixed by switching
   the whole highlight model from `(sentence_index, word_text)` to
   `(sentence_index, word_position)` -- the Nth word of the Mth
   sentence on screen, with no text comparison at all.
   `_speak_with_word_highlight()` now enumerates `timings` and passes
   the loop position; the render loop tracks each wrapped line's own
   starting word offset within its sentence
   (`[(page_index, word_offset, line), ...]`), and
   `_draw_reading_lines_static()` matches `word_offset + j ==
   target_position` instead of comparing text. `_normalize_word()`
   itself is now dead code and removed, along with its tests.

Four tests cover this: the last-word hold (asserts a sleep close to
the final word's own duration happens before the highlight clears,
via a patched `asyncio.sleep` that records delays instead of
waiting); position-based substitution still updating the highlighted
text correctly (unchanged in substance, just re-shaped as 3-tuples);
and a new test with two "and"s confirming every word gets its own
distinct position, none repeated.

## Consequences

Four new tests for `_speak_with_word_highlight()` (highlights each
word in order then clears; the cache-hit case makes exactly one
`tts.synthesize()` and one timestamp call across two invocations of
the same sentence/speed; graceful fallback when the backend lacks
the capability; graceful fallback when the lookup raises). Two new
tests on `OpenAIWhisperBackend` (request shape, including that the
audio sent is wrapped in a real WAV container; missing-API-key).
Four new tests on `reading/word_timing.py`'s pure parsing/wrapping.
Two new tests on `screen_face.py`'s `_normalize_word()`.

Full suite: 637 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged pre-existing baseline, no usable SDL video driver in
this dev environment).

## Not yet done

Not wired into word-family modeling (`_run_word_family_practice()`)
-- that already highlights each word correctly via
`set_word_grid_highlight()`, since each family word is spoken as its
own separate, single-word TTS call (no within-sentence timing
problem to solve there at all). Not wired into the whole-passage
cache surviving *across* separate calls to `_run_reading_partner()`
(e.g., a reread of a previously-finished exercise next session) --
scoped to one call only, matching the actual reuse scenario
described. If the same sentence is ever modeled at a *different*
speed than it was first cached at, this misses the cache and pays
for a fresh TTS+Whisper round trip rather than rescaling the cached
timestamps -- not implemented, since neither current call site
actually needs it (both model at the same `speed *
_MODEL_READ_SPEED_MULTIPLIER`).
