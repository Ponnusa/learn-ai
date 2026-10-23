# 0086 — Fix the teleprompter's clock and shorten the offer-reply wait

Date: 2026-10-23
Status: Accepted

## Context

Direct feedback from trying decision 0085 on real hardware: *"beep
comes very late.. also when chitti reads teleprompter doesnt move."*

## What was wrong

**Teleprompter frozen during modeling.** `set_reading_text()`
(`device/screen_face.py`) starts its own word-highlight clock
(`_reading_started_at`) the instant it's called -- not when anyone
actually starts reading. Decision 0085 called it once, early, so the
sentence stayed visible while the offer question was asked and its
reply captured (several real seconds of TTS synthesis + playback +
a beep-cued listen). By the time Chitti actually started modeling the
sentence -- or the child's own capture began -- that clock had
already run out, so the highlight animation had already finished (or
sat at its last word) before the one moment it was meant to track.
Confirmed by reading `_create_screen()`/the render loop's own
`elapsed = time.monotonic() - started_at` math, not just inferred
from the report.

**Offer reply using the wrong floor.** The yes/no reply to "Would you
like me to read it to you first?" was captured with
`_MIN_CAPTURE_SECONDS` (3.0s) -- the floor decision 0084 built for a
full *sentence* reply, not a one-word yes/no. Stacked on top of the
offer question's own synthesis and playback, this made the whole
exchange feel slow before the real reading-aloud beep was even
reached.

## What shipped

**`voice_loop_demo.py`**: `set_reading_text([sentence], ...)` is now
called again, resetting the highlight clock, right before each actual
reading moment -- once right before Chitti's own modeled speech (if
the offer was accepted), and once more right before the child's own
capture begins (whichever branch was taken). The original call before
the offer question is kept, so the sentence is still visible on
screen while the child is deciding/answering -- only the *animation
timing* needed a reset, not the visibility.

New constant `_OFFER_REPLY_CAPTURE_SECONDS = 1.5` (vs.
`_MIN_CAPTURE_SECONDS`'s 3.0), used only for the offer-reply capture.

## Consequences

Existing tests asserting an exact `face.reading_texts` sequence
updated for the extra reset call per sentence (each sentence now
shows twice in that list where it used to show once; decision 0074/
0081's reread step was already a separate, unaffected call).

Full suite: 614 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures).

## Not yet done

The teleprompter's highlight pace and the TTS's actual modeled-speech
pace are still not frame-synced -- both are just driven by the same
configured pace, same documented limitation as decision 0085. This
fix makes the highlight start at the *right moment*; it doesn't make
it track the real audio precisely throughout. `_OFFER_REPLY_CAPTURE_SECONDS`'s
value (1.5s) is a first guess, not validated against a real child's
reaction time yet.
