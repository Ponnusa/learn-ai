# 0085 — Ask before each sentence: read it yourself, or hear it first?

Date: 2026-10-23
Status: Accepted

## Context

A real transcript from the Pi, pasted directly: the story "Pat and
the Pup" printed its full text up front, then jumped straight into
"Press Enter to start talking..." for sentence 1 with no further
framing. Across the next two captures, the transcribed text kept
drifting from what was actually expected -- the first capture already
read ahead into later sentences, and the second capture restarted
from the beginning of the story instead of continuing. The product
owner's diagnosis, asked directly and confirmed: testing from the
terminal alone (no physical screen in view), there was no way to tell
which single sentence was currently expected -- the console prints
the whole story once at the top, then gives no per-sentence reminder
at all, unlike decisions 0053/0067's own screen-side highlighting.

The product owner's own fix, described directly and built exactly as
asked, one step at a time ("lets do one after another.. i will
instruct"): *"it needs to ask the child can u read this for me or do
u want me to read it first? if chld say yes, chitti should first read
correctly paced as the teleprompter moves from 1 word to another.
after this chitti will say now its turn and try it now after the
beep sound. then there will be a beep sound and the mic will start
listening to wat kid says, gives some time and stops and checks what
has been said."*

Phrased the actual spoken question as a plain yes/no ("Would you like
me to read it to you first?") rather than the literal either/or in the
request -- an either/or's "yes" is inherently ambiguous about which
option it affirms, while a direct yes/no reuses the same
`is_affirmative()` classifier this codebase already trusts everywhere
else, and still matches the product owner's own example mapping
("if child says yes, chitti should read first").

## What shipped

**`_run_reading_partner()`'s per-sentence loop** (v1 only, same
scoping as decision 0084): the old blind capture --

```
face.set_reading_text([sentence], ...)
spoken = await _capture_and_transcribe(stt)
```

-- is now:

1. Chitti asks "Would you like me to read it to you first?" and
   captures the reply via decision 0084's beep-cued
   `_capture_and_transcribe_after_beep(stt, audio, _MIN_CAPTURE_SECONDS)`.
2. If `is_affirmative()` of that reply is true: Chitti speaks the
   sentence itself at `speed * _MODEL_READ_SPEED_MULTIPLIER` (the same
   slower pace decision 0084 already uses for modeling), while the
   teleprompter highlight is already running from `set_reading_text()`
   above -- then "Now it's your turn! Try it after the beep."
3. Either way, the actual read-aloud capture is
   `_capture_and_transcribe_after_beep(stt, audio,
   _sentence_capture_seconds(sentence, reading_pace_wpm))` -- the same
   beep-cued, duration-sized listen decision 0084 built, not a
   keypress.

The story's own intro line dropped its "Give it a try -- read it out
loud to me" tail (now just `Here's your story, "{title}"!`), since
that framing is wrong once the actual choice happens per sentence,
right before that sentence's own capture.

This replaces the ONLY remaining `_capture_and_transcribe()` call in
v1's main per-sentence loop with the beep-cued path -- after this,
every capture in a v1 sentence's initial read-aloud and its post-hint
reread (decision 0084) goes through
`_capture_and_transcribe_after_beep()`. The hint ladder's own
per-stage retries, the word-meaning check, the comprehension
questions, and the word game are untouched -- still the original
keypress capture, deliberately, pending the same "try it, see how it
feels" review decision 0084 already deferred.

## Consequences

Every test in `test_voice_loop_demo_intent.py` that exercises
`_run_reading_partner()`'s main read-aloud now needs one extra
scripted reply (a declining `"no thanks"`) immediately before each
sentence's own read-aloud entry, reusing decision 0084's
`_patch_captures()` helper throughout (switched several tests that
were still on a raw single `patch(...)` over to it too). Tests
asserting `tts.synthesized` by a fixed index were re-derived for the
one extra spoken line (the offer question) now ahead of them. Two
tests using a counter-based side_effect function (the story-bank and
word-drill fallback tests) needed a leading declining reply inserted
into their own scripted sequence so their first REAL scripted reply
(the exercise's actual read-aloud text) still landed on the actual
read-aloud call, not the new offer call ahead of it.

Full suite: 614 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

Asking "Would you like me to read it to you first?" before every
single sentence of a multi-sentence story hasn't been tried on real
hardware yet -- for a longer passage this could read as repetitive,
and the product owner's own plan is to try this one step, then
instruct what comes next rather than have it guessed at here. The
modeled TTS speech and the teleprompter's word-by-word highlight are
not frame-synced to each other -- both are just driven by the same
`reading_pace_wpm`/`speed` knobs already in use elsewhere, which is
only an approximate match, not a real synchronization mechanism.
