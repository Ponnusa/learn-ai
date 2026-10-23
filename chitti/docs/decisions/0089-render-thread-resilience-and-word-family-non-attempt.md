# 0089 — Render thread survives a bad frame; one reply for a non-attempt word-family check

Date: 2026-10-23
Status: Accepted

## Context

Direct feedback from a real transcript: *"nine of the words were
displayed.. it was supposed to list all words and ask me to read but
nothing was shown on screen. it just went on and on."*

Two separate, real problems in that one report:

1. **Nothing shown on screen.** The word-family grid (decision 0084)
   should have appeared while Chitti asked "Can you read all of these
   words for me?" -- the log shows that happened (the question was
   asked, a capture followed), but nothing was visible. Checked the
   render loop (`device/screen_face.py`'s `_run()`): the entire per-
   frame drawing block -- spotlight, word grid, reading text, or the
   dot-matrix face -- ran with no exception handling at all. One bad
   frame anywhere in it (in the word grid's drawing, or anywhere else)
   would silently kill the whole daemon thread; the screen would
   freeze on its last good frame for the rest of the session, while
   Chitti kept talking and listening fine (a separate asyncio loop),
   with nothing in the logs to explain why. This exact shape --
   "it was working, then the screen stopped, nothing else looks
   wrong" -- had already come up once before (decision 0088's
   teleprompter report); this is the second time, and the module's
   own stated principle ("a display problem must never take down a
   real conversation session") had only ever been applied to the
   *initial* setup (missing pygame, no driver), never to a frame
   that's already rendering.

2. **"It just went on and on."** Traced directly: the child's reply
   to the one-take word-family capture was "I don't know." -- none of
   the four candidate words ("hat", "cat", "bat", "mat") were found in
   it, so `_run_word_family_practice()`'s per-word reaction loop gave
   *each* of the four its own full phonics-breakdown reaction
   ("Good try! The word is 'hat' -- 'h' like in 'hat'...") -- four
   consecutive ~8-second TTS round trips for a reply that never
   attempted any of them.

## What shipped

**`device/screen_face.py`**: the render loop's whole per-frame
drawing block is now wrapped in a `try/except Exception`, logging via
`logger.exception(...)` and skipping just that frame -- the thread
keeps running and recovers on its own the moment the content changes
to something that doesn't fail, instead of dying once and freezing
the screen for good.

**`voice_loop_demo.py`**, `_run_word_family_practice()`: after the
one-take capture, now checks which family words were actually found
in the reply (`matched = [w for w in family_words if
is_correct_answer(w, reading)]`). If none were, one short combined
line ("That's okay! Those words were hat, cat, bat, mat. Let's keep
going!") replaces four individual breakdowns. If at least one was
attempted, the existing per-word loop runs as before -- real partial
credit still gets real per-word feedback, this only collapses the
complete-non-attempt case.

## Consequences

New tests: `test_render_thread_survives_a_bad_frame`
(`test_screen_face_rendering.py`) -- monkeypatches `_draw_spotlight`
to raise once, confirms `health_check()` stays `True` and the thread
keeps calling it on later frames. `test_run_reading_partner_word_family_gives_one_reply_when_nothing_was_attempted`
(`test_voice_loop_demo_intent.py`) -- reproduces the exact "I don't
know" transcript, confirms the one combined line and that no
individual phonics-breakdown reaction is spoken.

Full suite: 607 passed (3 failures in `test_screen_face_rendering.py`
-- the 2 pre-existing ones plus the new resilience test, all for the
same reason: no usable SDL video driver in this dev environment, so
the render thread never actually starts to be tested against. Not a
regression from this fix; same root cause as the existing two,
confirmed by the identical log line in all three).

## Not yet done

The render-thread fix is a safety net, not a diagnosis -- it stops a
bad frame from taking down the whole session and logs it, but the
*actual* cause of "nothing shown" in the reported transcript is still
unconfirmed (no traceback was available from that session to check
against). If it recurs, the next occurrence should finally show up in
the logs as "face render thread: frame failed, skipping it" with a
real traceback underneath, which this fix makes possible to check for
the first time.
