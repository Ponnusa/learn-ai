# 0088 — Remove the moving teleprompter; show static text instead

Date: 2026-10-23
Status: Accepted

## Context

Direct feedback: *"the teleprompter is not at all sowing thw words
after some time.. it was working and the chitti speaks but i dont see
any word on teleprompter at all.. why"*, followed by: *"lets remove
the teleprompter kind of moving betwen words.. why not use somethin
like this git projects for teleprompter: [LE-VAI/read-along,
gabrielg2020/talkbox, liorwn/book-karaoke] ... check and let me know."*

Checked all three: `read-along` is a browser JS web component driven
by the Web Speech API's live word-boundary events or a pre-supplied
timing file -- not usable here (Chitti has no browser). `talkbox` and
`book-karaoke` both get real word-by-word sync, but only because they
pair with a TTS/alignment step Chitti doesn't have: `talkbox` needs
Kokoro, a local neural TTS that emits real per-word timestamps (too
heavy for the Pi 1 B+'s single ARMv6 core); `book-karaoke` re-runs
Whisper on its own synthesized audio afterward just to recover word
timestamps, and targets Apple Silicon specifically (mlx-whisper).
Reported back with the option to borrow book-karaoke's general
technique (synthesize, then timestamp Chitti's own TTS output via the
Whisper backend it already has) versus just dropping word-by-word
highlighting -- the product owner chose to drop it.

Separately, the earlier "words stopped showing" report pointed at a
real, structural problem worth fixing regardless of which direction
was chosen: the old auto-scrolling teleprompter (decision 0053)
highlighted words by tracking elapsed real time against a *simulated*
reading pace (`wpm`), not the actual audio -- already shown to desync
badly in decision 0086. Worse, its whole per-frame drawing block
(`_draw_teleprompter`, `_build_word_timeline`, font rendering) ran
with no exception handling in the render thread's `while
self._running:` loop -- any single bad frame would silently kill the
whole daemon thread, freezing the screen on its last good frame for
the rest of the session, while speech/listening (a separate asyncio
loop) kept working fine. That fully explains "it was working... then
stopped," independent of root-causing which specific frame failed.

## What shipped

**`device/screen_face.py`**: removed the whole timed auto-scroll
mechanism -- `TimedWord`, `_build_word_timeline()`,
`_current_word_index()`, `_draw_teleprompter()`, and the render
loop's `timeline_key`/`timeline_lines`/`timeline_words` caching state.
New `_draw_reading_lines_static()`: word-wraps (reusing the existing
`_wrap_text()`) and draws the sentence as plain, static text,
centered as one block, with no timing dependency and no highlighting
-- nothing left to desync, and nothing frame-by-frame expensive
enough to be a reasonable crash risk either way.

`set_reading_text()`'s `wpm` parameter is kept (not removed) for
backward compatibility -- every existing call site in
`voice_loop_demo.py` still passes `reading_pace_wpm`, and
`parent_controls`' own `reading_pace_wpm` profile setting still
writes through the same path unchanged. It's simply not read by the
render loop anymore; the docstring says so explicitly rather than
leaving that silently true.

## Consequences

`tests/unit/test_screen_face.py`: removed the `_build_word_timeline`/
`_current_word_index` tests along with their subjects; added direct
`_wrap_text()` tests (short line kept whole, long text wrapped, a
single word wider than max_width still gets its own line) since
`_build_word_timeline`'s tests were the only thing exercising
`_wrap_text()` before. `tests/unit/test_screen_face_rendering.py`'s
smoke test renamed (`test_reading_text_and_spotlight_render_without_crashing_the_thread`)
and no longer passes `wpm` (nothing left for it to affect).

Full suite: 606 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

The render loop's per-frame drawing still has no exception handling
of its own -- removing the timed auto-scroll removes the one concrete
crash risk found so far, but doesn't add the general safety net (catch
and log, keep the thread alive) that would also protect against a
*future* bad frame in whatever draws next (the spotlight, the word
grid, a new feature). Worth adding separately if this class of
problem recurs. `parent_controls`' `reading_pace_wpm` setting is now
fully inert from the screen's point of view -- not removed from the
schema or the parent-facing UI here, since that's a separate, larger
decision than "stop the words from moving."
