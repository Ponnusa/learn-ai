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

Full suite: 633 passed (4 failures in `test_screen_face_rendering.py`
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
