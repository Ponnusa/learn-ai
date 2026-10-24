# 0102 — Reduce OpenAI API call volume

Date: 2026-10-24
Status: Accepted

## Context

A real hardware session hit a 429 ("Too Many Requests") from
OpenAI's TTS endpoint mid-session. Counting the actual log
line-by-line (not guessing) showed why: one ~7-minute segment alone
made 64 TTS calls, 27 Whisper calls (19 child-capture + 8
word-timestamp lookups for decision 0098's highlight feature), and 6
logged LLM calls (plus 2 more -- word-family generation -- not even
logged, since `generate_word_family()` isn't wrapped in
`_generate_with_thinking_filler()`).

Decision 0101 already commented out `_speak_while_thinking()`'s call
as a stopgap -- a blunt lever that removed the filler *speech*, not
the underlying waste (the 3 filler lines are always the same fixed
text, so should never have needed a fresh API call in the first
place).

The user also pasted an outside AI's review of the same log and
asked for a plan. That review was written without seeing any code --
it guessed at an architecture ("run TTS on a more powerful machine")
that doesn't match reality (TTS already runs remotely via OpenAI's
API, decision 0016; the Pi only ever plays audio back via `aplay`,
never synthesizes locally) and recommended a response-type-enum
refactor that a simpler text-based cache makes unnecessary. This
decision keeps the parts of that review that held up against the
actual code and drops or adapts the rest.

**Explicitly out of scope**: the review's point about unreliable
speech recognition ("DRUG"/"RUN!" hint-ladder attempts, "hand pen
then 10" for a word-family capture, "10." answering "who wears the
red cap") is a real, separate problem -- answer-confidence handling,
not call volume. It deserves its own decision, not a bolt-on here.

## What shipped

**`voice/tts_cache.py`** (new): `TTSCache`, a `TextToSpeechBackend`
implementation wrapping any concrete backend transparently. Keyed by
`sha256(text|voice|model|speed)`; a cache hit reads raw PCM bytes
straight off disk (temp-file-then-rename on write, so an interrupted
write never leaves a truncated entry readable later) with no API
call at all. `hits`/`misses` counters for visibility. No size
cap/eviction for v1 -- the vocabulary at these reading levels is
naturally small and bounded.

**`voice_loop_demo.py`**, `setup_demo()`: `tts =
TTSCache(OpenAITTSBackend(), voice="alloy", model="tts-1", cache_dir=data_dir
/ "tts_cache")` -- none of the ~57 existing `_speak()` call sites
needed to change. `chitti/data/` is already entirely gitignored
(`.gitignore:66`), the same precedent `data_dir` already follows for
the SQLite DB and lullaby files.

Decision 0101's `_speak_while_thinking()` call in
`_generate_with_thinking_filler()` is **re-enabled** -- the 3 filler
lines are now a one-time cost (first-ever synthesis) instead of a
recurring one.

`run_mode_dispatch_loop()`'s `finally` block now logs `tts cache: N
hits, M misses` once per session.

**Word-family practice** (`_run_word_family_practice()`): the
`read_first=True` modeling loop spoke one word per TTS call (e.g. 4
calls for "hen"/"pen"/"den"/"ten"). The real-time word-highlight
mechanics decision 0098 built for sentence modeling
(`_speak_with_word_highlight()`) were extracted into a shared core,
`_speak_with_timed_highlight(tts, audio, stt, text, speed, cache,
on_word, on_done)`, parameterized by a highlight callback instead of
being hardcoded to the reading-text highlight. Word-family modeling
now speaks the whole family as **one** combined utterance ("Hen.
Pen. Den. Ten.") through this shared core, with `on_word` driving
`face.set_word_grid_highlight()` (normalized via `clean_word()`,
since the combined utterance's own tokenization keeps trailing
punctuation that the grid's exact-string match wouldn't otherwise
match) instead of the sentence path's position-based reading-text
highlight. Falls back to the original per-word loop whenever `stt`
lacks `transcribe_with_word_timestamps` at all -- with everything in
one combined clip, there's no other way to know which word is being
spoken. Net: 4 TTS calls -> 1 TTS + 1 Whisper call for a 4-word
family.

**Shared cache entry for a flagged sentence's two highlighted
reads**: "Let's work on this one: ..." and the later "I'll read it
for you first. Listen:" both read the same flagged sentence aloud
with highlighting, but at different speeds (`speed` vs. `speed *
_MODEL_READ_SPEED_MULTIPLIER`) -- different cache keys, so two
separate TTS+Whisper round trips for one sentence. The first read
now uses the same slower speed as the second, so both land on the
same `modeled_word_timings_cache` entry -- confirmed directly in a
test (`stt.timestamp_calls == 1` across both reads, was 2). Tradeoff,
stated plainly: the attention-cue's own read of the sentence is now
at the slower modeling pace instead of conversational pace.

## Consequences

New `test_tts_cache.py` (6 tests: miss calls the backend and writes
a file, hit never calls the backend again, different speed/voice/
model are different entries, a second `TTSCache` instance reuses a
first instance's disk entries, cache dir auto-created). New test for
the word-family combined-utterance path (one combined TTS call, grid
highlight still driven by real per-word timestamps). Extended
`test_run_reading_partner_highlight_uses_the_narrowed_display_page_not_the_story_index`
to assert the shared-cache claim directly. Reverted decision 0101's
two test changes (filler calls are expected again).

Full suite: 645 passed (4 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

No disk-cache size cap or eviction -- revisit only if disk usage on
the Pi's SD card actually becomes a real problem, not speculatively.
The answer-confidence/speech-recognition-reliability issue the
external review also raised is a deliberately separate, future
decision -- not folded into this one.
