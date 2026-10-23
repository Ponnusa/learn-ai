# 0087 — Remove the beep; fix a real misclassification in the new offer

Date: 2026-10-23
Status: Accepted

## Context

Direct feedback after trying decision 0086 on real hardware: *"lets
remove the beep altogther it looks very bad.. have enter for now.
also first time chitti didnt even read the sentecne for me, there is
some problem."*

Traced the second part against the actual transcript, not just the
complaint:

```
Chitti: Would you like me to read it to you first?
...
You said: you
...
You read: Yes. Yes.
Chitti: Let's try that word again -- take your time and sound it out.
```

The reply to "Would you like me to read it to you first?" was just
"you" (a completely natural way to answer -- short for "you read
it"). `classify_affirmative()`'s generic yes/no vocabulary doesn't
contain "you" at all, so it fell through to the default: decline,
skip modeling, go straight to listening for the child's own read.
That's a real, confirmed bug -- not just the beep feeling bad, a
second, independent problem in the same flow.

## What shipped

**Beep removed entirely**, not just switched off: deleted
`audio/tones.py` (`generate_beep()`), and from `voice_loop_demo.py`:
`_capture_and_transcribe_after_beep()`, `_record_clip_for_duration()`,
`_sentence_capture_seconds()`, and the `_MIN_CAPTURE_SECONDS`/
`_CAPTURE_BUFFER_SECONDS`/`_OFFER_REPLY_CAPTURE_SECONDS`/
`_FALLBACK_READING_PACE_WPM` constants -- all of it was dead weight
the moment every call site went back to `_capture_and_transcribe()`
(press Enter), so it was deleted rather than left unused. Every
capture in `_run_reading_partner()` -- the per-sentence offer reply,
the per-sentence read-aloud (whether or not Chitti modeled it first),
and the post-hint-ladder reread -- is back to the original
keypress-based capture. The two spoken cues that mentioned the beep
("Now it's your turn! Say/Try it after the beep.") now just say "Now
it's your turn! Give it a try."

**New `_classify_read_first_offer_reply(reply) -> bool`**: checked
first, ahead of `classify_affirmative()`, same local-to-one-question
pattern decision 0080's `_classify_reread_reply()` already
established -- if the reply contains "you" (as a whole word), it
means yes, read it to me first. Otherwise falls back to
`classify_affirmative()`, defaulting to `False` (the child reads it
themselves) for anything genuinely unclear -- the original,
always-safe default, never a guess toward the more demanding option.

The offer-to-model feature itself (decisions 0085/0086's "would you
like me to read it to you first?", the slower-paced modeled read, and
the teleprompter-clock-reset fix) is kept -- only the beep-cued
capture mechanism and this one classification bug were addressed
here.

## Consequences

Deleted `tests/unit/test_audio_tones.py` and the
`_sentence_capture_seconds` unit tests along with their subjects. New
tests for `_classify_read_first_offer_reply()`: recognizes "you"/"you
read it"/"you do it first" as yes (the exact reproduced bug), still
recognizes plain yes/no, defaults to `False` on unclear text. Every
test that patched `_capture_and_transcribe_after_beep()` (directly, or
via the `_patch_captures()` test helper) reverted to patching only
`_capture_and_transcribe()`; every assertion on the old "...after the
beep." cue text updated to "...Give it a try."

Full suite: 610 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures).

## Not yet done

"At least for now" is the product owner's own framing -- if a beep-
style cue is revisited later, this decision and 0084/0085/0086 are
the record of what was tried and why it didn't land; nothing here
prevents rebuilding it differently. The underlying latency this was
trying to solve (several real seconds of TTS synthesis/playback per
spoken cue, now even more of them per sentence between the offer and
the actual read) is unaddressed -- out of scope for this fix.
