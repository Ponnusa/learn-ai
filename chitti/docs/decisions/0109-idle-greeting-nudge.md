# 0109 — A fixed "anything for me?" nudge after an hour of no interaction

Date: 2026-10-24
Status: Accepted

## Context

Direct follow-up to decision 0108, after discussing whether a
generic (non-LLM) greeting could also cover the "comes alive again
after being idle" case:

> "My recommendation: use "Hey, [name]! I'm here if you want to
> read, play, or tell me something!" after 60 minutes of
> inactivity. It gives the child several ways to engage, not just
> reading."

Confirmed against the real architecture first: `voice_loop_demo.py`
is explicitly push-to-talk (decision 0016) -- `_capture_and_transcribe()`
blocks on a literal Enter keypress. There is no background listening
loop, so Chitti can never truly volunteer speech while nobody is
there. The earliest it can say anything is the next time someone
*does* press Enter -- so "comes alive after 60 minutes idle" means,
concretely: the next turn that starts after a 60+ minute gap opens
with this fixed line, spoken before whatever the child actually
says is processed.

Unlike decision 0018/0108's welcome-back recap, this line has
nothing to personalize beyond the child's own name, so it never
calls an LLM -- `TTSCache` (decision 0102) ends up paying to
synthesize it only once per child, ever, no matter how many times it
fires after that.

## What shipped

**`voice_loop_demo.py`**: `_IDLE_GREETING_AFTER = timedelta(minutes=60)`,
a module-level `_last_interaction_at: datetime | None` (in-memory
only -- a live clock for however long the process keeps running, not
a historical record the way decision 0108's `last_greeted_date` is),
`_idle_greeting_text(child_name)`, and `_maybe_speak_idle_greeting(tts,
audio, face, speed, child_name)`: speaks the line (and resets the
clock) if the gap since the last check is >= 60 minutes, otherwise
just resets the clock. `None` until the first check ever runs, so a
freshly started process's very first turn never triggers it.

Wired into the top of each of the five mode loops' own "wait for the
next turn" point, right before `_capture_and_transcribe()` (chat-style
modes: Teachable-Friend, Just Chat, Story Companion) or at the very
top of the outer loop (Reading Partner v1 and v2, where book/exercise
selection -- not a capture call -- comes first each iteration). Each
of those five functions gained one new, defaulted `child_name: str =
""` parameter (default keeps every existing test call site working
unchanged); `run_mode_dispatch_loop()`'s four real call sites (the
fifth, Reading Partner, is one shared call behind a v1/v2 toggle)
now pass `child_name=ctx.profile.name`.

Deliberately NOT added to the many secondary, sub-dialog capture
calls inside Reading Partner (confirm-switch, reread offers, word
game, word-family practice, etc.) -- those happen in quick
succession right after Chitti has just spoken, so a genuine 60-minute
gap realistically only ever opens at the top of a mode's own main
loop, not mid-exchange.

## Consequences

Five new unit tests in `test_voice_loop_demo_idle_greeting.py`
(`_idle_greeting_text` includes the name; silent on the very first
call ever; silent within the 60-minute window; speaks after 60
minutes; doesn't repeat itself right after speaking). Two new
integration tests in `test_voice_loop_demo_intent.py` confirming the
hook is actually wired into two differently-shaped real loops
(Teachable-Friend's capture-adjacent check, Reading Partner's
top-of-loop check) -- not just unit-tested in isolation.

Full suite: 693 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment; a separate run surfaced
`test_claude_backend.py`/`test_audio_real.py` failures that did not
reproduce on rerun and pass cleanly in isolation -- pre-existing
test-suite flakiness, not something this change caused).

## Not yet done

No per-mode or per-child override of the 60-minute threshold --
hardcoded, same "minimal first version" choice as everything else
here. If a parent ever wants it tuned, that's a small, separable
follow-up (another `ChildProfile` field, same shape as
`reading_pace_wpm`).
