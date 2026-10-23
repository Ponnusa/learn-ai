# 0094 — The "read it to you first?" choice holds for the whole session

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback: *"durng the excersive for the stroy or session if
the child says yes to Would you like me to read it to you first?
from then chitti must always speak the word first until the next
session. so that should also go for the list of similar words where
chitti should speak alwasy first.. also chitti must read the whole
story first not sentecne by sentence. thats make osut life easier..
isnt it.."*

Decision 0085 asked "Would you like me to read it to you first?"
fresh for every single sentence, and modeled only that one sentence
when accepted. Re-asking the same question dozens of times in one
story, and never letting a "yes" carry forward, is exactly the
repetitive friction being described here.

## What shipped

**`voice_loop_demo.py`**, `_run_reading_partner()`: a new
session-scoped `read_first_preference: bool | None = None`, declared
once alongside the other per-call trackers (`offered_reread`,
`consumed_this_call`, `followup_source_text`) -- outside the
`while True:` book loop, so it survives across every book in one call
but starts fresh (`None`, meaning "not decided yet") on the next
fresh call to this function. That's the actual scope of "until the
next session": one call to `_run_reading_partner()`, which may cover
several books, not one sentence or one book.

The offer is now asked at most once per call -- the first time it's
needed, right after the whole story is shown on screen (decision
0093) and before the per-sentence capture loop starts. Once answered,
`read_first_preference` holds that answer for every remaining
sentence in the current book AND every later book in the same call;
the per-sentence offer-ask and per-sentence modeling that used to sit
inside the capture loop are both gone.

When the preference is `True`, Chitti now models the *entire*
remaining story in one continuous read-through (`sentences[start_index:]`,
each spoken at the slower modeled pace, back to back, no captures in
between) before a single "Now it's your turn! Let's read it together,
one sentence at a time." cue -- not interleaved sentence-by-sentence
with the child's own attempts. The child's own reading stays
per-sentence after that (decision 0067's own reasoning for that --
easier for a young child to sustain, kinder to STT accuracy -- still
applies to listening, even though modeling no longer needs it).

`_run_word_family_practice()` gained a `read_first: bool = False`
parameter, passed from its one call site as
`read_first=bool(read_first_preference)`. When true, Chitti now says
"Let's read these together. Listen first:", speaks every word in the
family aloud (same modeled pace), then asks "Now it's your turn! Can
you read all of these words for me?" -- instead of asking cold.

Scoped to v1 only, same as every decision in this series since 0084;
`_run_reading_partner_v2()` is untouched.

## Consequences

Eight existing tests updated for the new, single-offer-per-call
shape: each one's scripted capture list had one offer-reply removed
per extra sentence/book that no longer asks again, with comments
rewritten to say why. One test's own premise (the reread-offer test)
was unaffected in substance -- only the capture list needed the same
mechanical fix, since its real subject (decision 0079/0080) is
untouched by this change.

Full suite: 613 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged from decision 0093's baseline, same root cause: no
usable SDL video driver in this dev environment).

## Not yet done

The post-hint-ladder reread step (decisions 0074/0081/0084) still
unconditionally models the sentence before asking for the reread,
regardless of `read_first_preference` -- not changed here, since the
request was about the initial per-sentence/per-word-family choice,
not this later, remedial step (which runs only after the child has
already struggled with the word once, a different context from the
up-front choice).
